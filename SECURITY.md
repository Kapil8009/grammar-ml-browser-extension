# Security

## Supported version

Security fixes are applied to the latest release on the default branch.

## Reporting

Do not open a public issue for a vulnerability that exposes user text, credentials, or remote execution. Contact the repository owner privately with reproduction details and affected versions.

## Deployment checklist

- Serve the API over HTTPS.
- Set a strong `GEC_API_KEY` and avoid committing it.
- Restrict `GEC_ALLOWED_ORIGINS` to known extension/application origins.
- Pin model and Python dependency versions for production builds.
- Pin `GEC_MODEL_REVISION` to a reviewed Hub commit.
- Keep model loading with `trust_remote_code=False`.
- Add infrastructure rate limits and request logging that redacts text and API keys.
