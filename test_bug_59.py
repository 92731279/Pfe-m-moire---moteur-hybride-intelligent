import asyncio
from src.pipeline import run_pipeline
from src.pipeline_logger import PipelineLogger

class SilLevelLogger(PipelineLogger):
    def log(self, step, message, level="INFO", **data):
        print(f"[{step}] {message} {data}")

res, _ = run_pipeline(
    raw_message=":59:/TN5903603077019102980938\nSTE AUTOMATISME INDUSTRIEL\nCITE ERRIADH Ariana\nTUNISIE",
    message_id="BUG_59",
    slm_model="qwen2.5:0.5b",
    logger=SilLevelLogger()
)

print(f"REJECTED: {res.meta.rejected}")
print(f"REASONS: {res.meta.rejection_reasons}")
print(f"WARNINGS: {res.meta.warnings}")
print(f"CONFIDENCE: {res.meta.parse_confidence}")
