from lion import availability as lion_availability
from proof import availability as proof_availability

from . import availability as vision_availability


def integrated_availability() -> dict[str, str]:
    return {
        "PROOF": proof_availability(),
        "LION": lion_availability(),
        "VISION": vision_availability(),
    }
