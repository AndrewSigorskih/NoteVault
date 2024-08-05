import json
import sys
from logging import getLogger
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ValidationError

logger = getLogger()
CONFIGFILENAME = "config.json"
HASHFILENAME = "hash" # TODO change this to hidden filename


class AppConfig(BaseModel):
    storage_pth: Path
    password_salt: str

    # Cannot serialize Path objects without that
    class Config:
        json_encoders = {
            Path: lambda v: str(v)
        }

    def model_post_init(self, __context: Any):
        hash_file_path = self.storage_pth / HASHFILENAME
        if hash_file_path.exists():
            try:
                with open(self.storage_pth / HASHFILENAME, "rb") as f:
                    self._password_hash = f.read()
            except Exception as e:
                import traceback
                logger.error("Error while reading binary secrets file:")
                print(traceback.format_exc())
                sys.exit(1)
        else:
            self._password_hash = None

    @property
    def password_hash(self) -> bytes:
        if self._password_hash:
            return self._password_hash
        else:
            logger.error("Error: key hash was not initialized!")
            sys.exit(1)
    
    @password_hash.setter
    def password_hash(self, pwd_hash: bytes) -> None:
        self._password_hash = pwd_hash
    
    @classmethod
    def from_json(cls, path: Path) -> "AppConfig":
        try:
            with open(path, "r") as f:
                obj = cls(**json.load(f))
        except ValidationError as e:
            logger.error("Error while parsing configuration file:")
            for error in e.errors():
                print(f"{error.type} : got {error.input}, failed with : {error.msg}")
                sys.exit(1)
        except Exception as e:
            import traceback
            logger.error("Could not load configuration file:")
            print(traceback.format_exc())
            sys.exit(1)
        return obj

    def dump(self) -> None:
        with open(self.storage_pth / CONFIGFILENAME, "w") as o:
            print(
                self.model_dump_json(indent=2),
                file=o
            )
        with open(self.storage_pth / HASHFILENAME, "wb") as o:
            o.write(self._password_hash)
