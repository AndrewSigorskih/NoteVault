import argparse
import os
import sys
from enum import Enum
from functools import total_ordering
from logging import getLogger
from pathlib import Path
from typing import Optional

# For Linux/Wayland users.
if os.getenv("XDG_SESSION_TYPE") == "wayland":
    os.environ["XDG_SESSION_TYPE"] = "x11"

import glfw
import OpenGL.GL as gl
import imgui
from imgui.integrations.glfw import GlfwRenderer

from .config import AppConfig, CONFIGFILENAME
from .database import Database
from .logger import configure_logger, VERBOSE
from .password import (
    Encoder, gen_salt, password_meets_requirements, verify_password,
    PASSWORD_REQUIREMENTS
)


APPNAME = "NoteVault"
path_to_font = None  # "path/to/font.ttf"
WIDTH, HEIGHT = 1600, 900

logger = getLogger()


@total_ordering
class AppState(Enum):
    HARDRESET = -100
    CONFIRMHARDRESET = -99
    CONFIRMHARDRESETFAILED = -98

    INVALIDNEWPASSWORD = -2
    EMPTY = -1

    LOGGEDOFF = 0
    INVALIDPASSWORD = 1

    LOGGEDON = 2
    ADDRECORD = 3
    FINDRECORD = 4
    DELETERECORD = 5
    RECORDFOUND = 6
    RECORDNOTFOUND = 7

    CHANGEPASSWORD = 100
    CHANGEPASSWORDFAILED = 101

    def __lt__(self, other):
        if self.__class__ is other.__class__:
            return self.value < other.value
        return NotImplemented


WINDOW_SIZES = {
    AppState.EMPTY : (400, 200),
    AppState.INVALIDNEWPASSWORD: (400, 150),
    AppState.LOGGEDOFF: (400, 200),
    AppState.INVALIDPASSWORD: (400, 120),
}


def impl_glfw_init():
    window_name = f"{APPNAME} -- a minimalistic secure notes storage app"

    if not glfw.init():
        logger.error("Could not initialize OpenGL context")
        sys.exit(1)

    glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
    glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 3)
    glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)
    glfw.window_hint(glfw.OPENGL_FORWARD_COMPAT, gl.GL_TRUE)

    window = glfw.create_window(int(WIDTH), int(HEIGHT), window_name, None, None)
    glfw.make_context_current(window)

    if not window:
        glfw.terminate()
        logger.error("Could not initialize Window")
        sys.exit(1)

    return window


class App:
    def __init__(self, custom_dir: Optional[Path]):
        # lifetime variables
        self.encoder = None
        self.user_input = ""
        self.user_input2 = ""

        # create/load configuration
        if custom_dir:
            custom_dir = custom_dir.resolve()
            if not custom_dir.exists() or not custom_dir.is_dir():
                logger.error(f"Provided custom storage path {custom_dir} is not a directory or does not exist!")
                sys.exit(1)
            storage_pth = custom_dir
        else:
            storage_pth = Path.home() / ".config" / APPNAME
            if not storage_pth.exists():
                storage_pth.mkdir(parents=True)
            
        logger.log(VERBOSE, f"Selected app context: {storage_pth}")

        cfg_pth = storage_pth / CONFIGFILENAME

        if cfg_pth.exists():
            logger.debug("Loading existing config")
            self.config = AppConfig.from_json(cfg_pth)
            self.state = AppState.LOGGEDOFF
        else:
            logger.debug("Setting up new configuration")
            self.config = AppConfig(
                storage_pth=storage_pth,
                password_salt=gen_salt()
            )
            self.state = AppState.EMPTY

        self.db = Database(storage_pth)
        
        

    def run(self):
        imgui.create_context()
        self.main_window = impl_glfw_init()

        impl = GlfwRenderer(self.main_window)

        io = imgui.get_io()
        jb = \
            io.fonts.add_font_from_file_ttf(path_to_font, 30) if path_to_font is not None \
                else None
        impl.refresh_font_texture()

        while not glfw.window_should_close(self.main_window):
            self.render_frame(impl, self.main_window, jb)

        impl.shutdown()
        glfw.terminate()
        self.db.close()
        # TODO remove imgui.ini  

    def render_frame(self, impl, window, font):
        glfw.poll_events()
        impl.process_inputs()
        imgui.new_frame()

        gl.glClearColor(0.1, 0.1, 0.1, 1)
        gl.glClear(gl.GL_COLOR_BUFFER_BIT)

        if font is not None:
            imgui.push_font(font)
        self.frame_commands()
        if font is not None:
            imgui.pop_font()

        imgui.render()
        impl.render(imgui.get_draw_data())
        glfw.swap_buffers(window)

    def center_new_window(self) -> None:
        main_win_width, main_win_height = glfw.get_window_size(self.main_window)
        curr_win_width, curr_win_height = WINDOW_SIZES[self.state]
        imgui.set_next_window_size(curr_win_width, curr_win_height)
        imgui.set_next_window_position(
            (main_win_width - curr_win_width) / 2,
            (main_win_height - curr_win_height) / 2
        )

    def frame_commands(self):
        io = imgui.get_io()
        if io.key_ctrl and io.keys_down[glfw.KEY_Q]:
            sys.exit(0)

        with imgui.begin_main_menu_bar() as main_menu_bar:
            if main_menu_bar.opened:
                with imgui.begin_menu("File", True) as file_menu:
                    if file_menu.opened:
                        clicked_quit, selected_quit = imgui.menu_item("Quit", "Ctrl+Q")
                        if clicked_quit:
                            sys.exit(0)
                # only allow reset actions when logged on
                if self.state >= AppState.LOGGEDON:
                    with imgui.begin_menu("Reset..", True) as reset_menu:
                        if reset_menu.opened:
                            clicked_change_pwd, _ = imgui.menu_item("Change password", "")
                            if clicked_change_pwd:
                                logger.log(VERBOSE, "User selected change password")
                                self.state = AppState.CHANGEPASSWORD #TODO add mode
                            clicked_reset, _ = imgui.menu_item("Delete all data", "")
                            if clicked_reset:
                                logger.log(VERBOSE, "User selected hard reset") # TODO debug print
                                self.state = AppState.CONFIRMHARDRESET # TODO add mode

        if self.state == AppState.EMPTY:
            self.center_new_window()
            with imgui.begin("Set new password to begin"):
                imgui.text("Input your new password and confirm:")
                imgui.text(PASSWORD_REQUIREMENTS)
                _, self.user_input = imgui.input_text(
                    "",
                    self.user_input,
                    256,
                    imgui.INPUT_TEXT_PASSWORD
                )
                confirm_clicked = imgui.button("Confirm")
                if confirm_clicked and len(self.user_input):
                    logger.debug(f"User input is {self.user_input}") # TODO debug print
                    if password_meets_requirements(self.user_input):
                        self.encoder = Encoder(self.user_input, self.config.password_salt)
                        self.config.password_hash = self.encoder.password_hash
                        self.config.dump()
                        # TODO init  database
                        self.state = AppState.LOGGEDOFF
                    else:
                        self.state = AppState.INVALIDNEWPASSWORD
                    self.user_input = ""
        
        elif self.state == AppState.INVALIDNEWPASSWORD:
            self.center_new_window()
            with imgui.begin("Error: provided password did not satisfy requirements!"):
                imgui.text(PASSWORD_REQUIREMENTS)
                confirm_clicked = imgui.button("Try again")
                if confirm_clicked:
                    self.state = AppState.EMPTY
        
        elif self.state == AppState.LOGGEDOFF:
            self.center_new_window()
            with imgui.begin(f"Welcome to {APPNAME}!"):
                imgui.text("Please enter your password:")
                _, self.user_input = imgui.input_text(
                    "",
                    self.user_input,
                    256,
                    imgui.INPUT_TEXT_PASSWORD
                )
                confirm_clicked = imgui.button("Log in")
                if confirm_clicked and len(self.user_input):
                    if verify_password(
                        self.user_input,
                        self.config.password_salt,
                        self.config.password_hash
                    ):
                        logger.log(VERBOSE, "User login cussessfull!")
                        self.encoder = Encoder(self.user_input, self.config.password_salt)
                        self.state = AppState.LOGGEDON
                    else:
                        logger.log(VERBOSE, "User login failed: incorrect password provided!")
                        self.state = AppState.INVALIDPASSWORD
                    self.user_input = ""

        elif self.state == AppState.INVALIDPASSWORD:
            self.center_new_window()
            with imgui.begin("Error: wrong password!"):
                imgui.text("The app remains locked..")
                confirm_clicked = imgui.button("Try again")
                if confirm_clicked:
                    self.state = AppState.LOGGEDOFF

        elif (self.state >= AppState.LOGGEDON) and (self.state <= AppState.RECORDNOTFOUND):
            self.draw_main_options_menu()
            if self.state == AppState.ADDRECORD:
                # https://pyimgui.readthedocs.io/en/latest/reference/imgui.core.html#imgui.core.input_text_multiline
                imgui.set_next_window_size(800, 300)
                with imgui.begin("Enter note title and body:"):
                    with imgui.begin_child("Title input", 200, 50):
                        _, self.user_input = imgui.input_text(
                        "",
                        self.user_input,
                        256,
                        )

                    _, self.user_input2 = imgui.input_text_multiline(
                        "",
                        self.user_input2,
                        -1
                    )
                    confirm_clicked = imgui.button("Confirm")
                    if confirm_clicked and len(self.user_input) and len(self.user_input2):
                        # TODO remove these prints
                        logger.debug(
                            "User inputted the following note:"
                            f"{self.user_input}\n"
                            f"{self.user_input2}"
                        )
                        logger.debug(
                                "Incrypted message:"
                                f"{self.encoder.encode(self.user_input)}\n"
                                f"{self.encoder.encode(self.user_input2)}"
                            )
                        # self.db.add_record(
                        #     self.encoder.encode(self.user_input),
                        #     self.encoder.encode(self.user_input2)
                        # )
                        self.user_input, self.user_input2 = "", ""
                        self.state=AppState.LOGGEDON
            elif self.state == AppState.FINDRECORD:
                # TODO open find record menu
                # set app state to recordfound or recordnotfound
                pass
            elif self.state == AppState.RECORDFOUND:
                pass
            elif self.state == AppState.RECORDNOTFOUND:
                pass
            

    def draw_main_options_menu(self) -> None:
        imgui.set_next_window_size(100, 80)
        imgui.set_next_window_position(0, 40)
        with imgui.begin("Options:"):
            add_btn = imgui.button("Add note")
            find_btn = imgui.button("Find note")
            if add_btn:
                self.state = AppState.ADDRECORD
            if find_btn:
                self.state = AppState.FINDRECORD


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-d", "--storage-dir", 
        required=False, type=Path,
        help="""An alternative path to store application data. Must be an existing directory."""
    )
    parser.add_argument("-v", "--verbose", action="count", default=0,
                        help="""Verbosity level. By default little to none information is printed.
Use -v once to get information logs about program state, and -vv to print detailed debug information.""")
    return parser.parse_args()
        

def main():
    args=parse_args()
    configure_logger(logger, args.verbose)
    App(args.storage_dir).run()


if __name__ == "__main__":
    main()
