from typing import Callable
from threading import Lock
from secrets import compare_digest

from modules import shared
from modules.api.api import decode_base64_to_image
from modules.call_queue import queue_lock
from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from src.gradio_demo import SadTalker
import api_models as models
import base64,os,uuid


class Api:
    def __init__(self, app: FastAPI, queue_lock: Lock, prefix: str = None) -> None:
        if shared.cmd_opts.api_auth:
            self.credentials = dict()
            for auth in shared.cmd_opts.api_auth.split(","):
                user, password = auth.split(":")
                self.credentials[user] = password

        self.app = app
        self.queue_lock = queue_lock
        self.prefix = prefix

        self.add_api_route(
            'video',
            self.video,
            methods=['POST'],
            response_model=models.SadTalkerResponse
        )

    def auth(self, creds: HTTPBasicCredentials = Depends(HTTPBasic())):
        if creds.username in self.credentials:
            if compare_digest(creds.password, self.credentials[creds.username]):
                return True

        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password",
            headers={
                "WWW-Authenticate": "Basic"
            })

    def add_api_route(self, path: str, endpoint: Callable, **kwargs):
        if self.prefix:
            path = f'{self.prefix}/{path}'

        if shared.cmd_opts.api_auth:
            return self.app.add_api_route(path, endpoint, dependencies=[Depends(self.auth)], **kwargs)
        return self.app.add_api_route(path, endpoint, **kwargs)

    def video(self, req: models.SadTalkerRequest):
        if req.image is None:
            raise HTTPException(404, 'Image not found')

        if req.audio is None:
            raise HTTPException(404, 'Audio not found')

        image_data = base64.b64decode(req.image)
        audiodata = base64.b64decode(req.audio)
        file_image = str(uuid.uuid4()) + ".png"
        file_audio = str(uuid.uuid4()) + ".wav"
        with open(file_image, "wb") as fh:
            fh.write(image_data)
        with open(file_audio, "wb") as fh:
            fh.write(audiodata)
        image_path = os.path.join(os.path.abspath('.'), file_image)
        audio_path = os.path.join(os.path.abspath('.'), file_audio)
        sad_talker = SadTalker(checkpoint_path="extensions/SadTalker/checkpoints",config_path="extensions/SadTalker/src/config",lazy_load=True)
        path = sad_talker.test(image_path,audio_path,result_dir="outputs/SadTalker")
        return models.SadTalkerResponse(
            video=encode_base64(path.replace("./", ""))
        )


def on_app_started(_, app: FastAPI):
    Api(app, queue_lock, '/sadtalker/v1')

def encode_base64(file):
    encoded = base64.b64encode(open(file, 'rb').read())
    return encoded