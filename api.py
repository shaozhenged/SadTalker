from typing import Callable
from threading import Lock
from secrets import compare_digest

from libs.qiniu_download import QiniuDownload
from modules import shared
from modules.api.api import decode_base64_to_image
from modules.call_queue import queue_lock
from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from src.gradio_demo import SadTalker
import api_models as models
import base64, os, uuid
from libs.global_config import TTS_IMAGE_DIR, LOGGER
from sound.tcloud_tts import TCloudTTS


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
        if req.image_url is None:
            raise HTTPException(404, 'image url not found')

        if req.audio_text is None:
            raise HTTPException(404, 'audio text not found')

        LOGGER.info(f"beginning image and audio to video task, image key={req.image_url}, audio_text={req.audio_text}, voice_type={req.voice_type}")

        img, img_bytes = QiniuDownload().download(req.image_url)

        file_name = f"{uuid.uuid4()}.{img.format.lower()}"
        file_name_fully = os.path.join(TTS_IMAGE_DIR, file_name)
        with open(file_name_fully, 'wb') as f:
            f.write(img_bytes)

        file_audio_path = TCloudTTS.text2video(req.audio_text, req.voice_type)
        sad_talker = SadTalker(checkpoint_path="extensions/SadTalker/checkpoints",
                               config_path="extensions/SadTalker/src/config", lazy_load=True)
        path = sad_talker.test(file_name_fully, file_audio_path, result_dir="outputs/SadTalker")
        return models.SadTalkerResponse(
            video=encode_base64(path.replace("./", ""))
        )


def on_app_started(_, app: FastAPI):
    Api(app, queue_lock, '/sadtalker/v1')


def encode_base64(file):
    encoded = base64.b64encode(open(file, 'rb').read())
    return encoded
