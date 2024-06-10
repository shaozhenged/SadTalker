from typing import List, Dict

from modules.api import models as sd_models
from pydantic import BaseModel, Field


class SadTalkerRequest(sd_models.BaseModel):
    image_url: str = Field(
        title='image_url',
        description="Image url to download"
    )

    audio_text: str = Field(
        title='audio text',
        description="text to be synthetise to audio"
    )

    voice_type: int = Field(title='voice type',
                            description="voice type",
                            default=1009)


class SadTalkerResponse(BaseModel):
    video: str = Field(
        title='Video',
        description='The generated image in base64 format.'
    )
