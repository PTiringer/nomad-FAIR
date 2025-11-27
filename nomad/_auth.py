from nomad.config import config
from nomad.config.models.config import _DEFAULT_API_KEY, ModeEnum


def check_api_secret() -> None:
    if (
        config.services.mode == ModeEnum.PRODUCTION
        and config.services.api_secret == _DEFAULT_API_KEY
    ):
        raise ValueError(
            'When running NOMAD in production mode, value for config.services.api_secret must be set to a minimum 32 character string through the environment variable NOMAD_SERVICES_API_SECRET. '
            'Alternatively you can run NOMAD in an insecure development mode by setting config.services.mode to development.'
        )
