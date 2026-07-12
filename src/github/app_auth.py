import time
import jwt  # PyJWT library
import requests


def generate_app_jwt(app_id: str, private_key: str) -> str:
    """
    Creates a short-lived JWT proving our identity as the GitHub App
    itself (not any specific installation). This is STEP 2 from our
    diagram — signing with the private key GitHub gave us at App
    registration.
    
    Args:
        app_id: the numeric App ID from GitHub App settings
        private_key: the full contents of the .pem file GitHub gave us
    
    Returns:
        A signed JWT string, valid for ~10 minutes
    """
    now = int(time.time())
    payload = {
        "iat": now - 60,        # issued at (60s in the past — 
                                  # accounts for clock drift between 
                                  # our server and GitHub's)
        "exp": now + (10 * 60),  # expires in 10 minutes — GitHub's 
                                  # maximum allowed lifetime for App JWTs
        "iss": app_id,           # issuer — proves WHICH app this is
    }
    return jwt.encode(payload, private_key, algorithm="RS256")


def get_installation_token(app_id: str, private_key: str, installation_id: str) -> str:
    """
    Exchanges our App-level JWT for a short-lived Installation Access
    Token, scoped to ONE specific installation (one repo/org that 
    installed our app). This is STEPS 3-4 from our diagram.
    
    Args:
        app_id: the numeric App ID
        private_key: the .pem file contents
        installation_id: which installation we want a token for —
                          this comes from the webhook payload GitHub
                          sends us when a PR event fires
    
    Returns:
        A short-lived installation access token (~1 hour), usable
        exactly like a personal access token for API calls scoped
        to what this installation permitted
    """
    app_jwt = generate_app_jwt(app_id, private_key)

    response = requests.post(
        f"https://api.github.com/app/installations/{installation_id}/access_tokens",
        headers={
            "Authorization": f"Bearer {app_jwt}",
            "Accept": "application/vnd.github+json",
        },
        timeout=10,
    )
    response.raise_for_status()  # raises an exception on 4xx/5xx

    return response.json()["token"]