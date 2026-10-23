"""The only backend in this package: writes a bounded JSON fixture, no processes."""

import os

from .models import bytes_digest, fixed_fake_content, require
from .paths import result_path


class FakeBackend:
    def emit(self, context, plan, run):
        path = result_path(context, run["run_id"])
        require(not path.parent.exists(), "OUTPUT_CONFLICT", "Run output directory already exists")
        path.parent.parent.mkdir(exist_ok=True)
        path.parent.mkdir(exist_ok=False)
        content = fixed_fake_content(plan, run)
        require(len(content) <= plan["resources"]["max_output_bytes"], "RESOURCE_LIMIT", "Fake output exceeds budget")
        with path.open("xb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        return {"path": str(path), "digest": bytes_digest(content), "size": len(content)}
