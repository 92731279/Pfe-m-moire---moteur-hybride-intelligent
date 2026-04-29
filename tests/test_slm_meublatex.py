import asyncio
from src.pipeline import run_pipeline
from src.pipeline_logger import PipelineLogger

class SilLevelLogger(PipelineLogger):
    def log(self, step, message, level="INFO", **data):
        print(f"[{step}] {message} {data}")

res, _ = run_pipeline(
    raw_message=":50K:/TN4839\nARIANA\navenue de l'uma La soukra\nSOCIETE MEUBLATEX SA\nATTN DIR FINANCIER",
    message_id="BUG_MEUBLATEX",
    slm_model="qwen2.5:0.5b",
    logger=SilLevelLogger()
)
import json
print(json.dumps(res.model_dump(), indent=2, default=str))
