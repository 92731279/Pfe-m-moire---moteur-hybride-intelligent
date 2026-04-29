import asyncio
from src.pipeline import run_pipeline
from src.pipeline_logger import PipelineLogger

class SilLevelLogger(PipelineLogger):
    def log(self, step, message, level="INFO", **data):
        pass

res, _ = run_pipeline(
    raw_message=":50K:/TN4839\n\navenue de l'uma La soukra\nSOCIETE MEUBLATEX SA\nATTN DIR FINANCIER",
    message_id="BUG_MEUBLATEX_USER",
    slm_model="qwen2.5:0.5b",
    logger=SilLevelLogger()
)
print("REJECTED:", res.meta.rejected)
print("TOWN:", res.country_town.town)
print("WARNINGS:", res.meta.warnings)
