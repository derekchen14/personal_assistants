# OAuth provider configurations
# Add provider entries following this structure. Each provider needs:
#   auth_url       - where users are redirected to grant access
#   token_url      - endpoint to exchange auth code for access token
#   user_info_url  - endpoint to fetch authenticated user info
#   scopes         - list of permission scopes to request
#   id_field       - key in user_info response that holds the provider user ID
#   token_request  - details for the token exchange HTTP request

PROVIDER_CONFIG = {
  "example_provider": {
    "auth_url": "https://provider.example.com/oauth/authorize",
    "token_url": "https://provider.example.com/oauth/token",
    "user_info_url": "https://provider.example.com/api/userinfo",
    "scopes": [
      "read:data",
      "read:profile"
    ],
    "id_field": "user_id",
    "token_request": {
      "url": "https://provider.example.com/oauth/token",
      "headers": {
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json"
      },
      "payload_template": {
        "grant_type": "authorization_code",
        "redirect_uri": "{redirect_uri}",
        "code": "{code}"
      }
    }
  }
}
