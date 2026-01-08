import os
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware import Middleware
from fastapi.middleware.cors import CORSMiddleware
from fastapi_keycloak_middleware import KeycloakMiddleware, get_user, KeycloakConfiguration, require_permission
from fastapi_keycloak_middleware.fast_api_user import FastApiUser

# Load environment variables
KEYCLOAK_SERVER_URL = os.getenv("KEYCLOAK_SERVER_URL")
KEYCLOAK_REALM = os.getenv("KEYCLOAK_REALM")
KEYCLOAK_CLIENT_ID = os.getenv("KEYCLOAK_CLIENT_ID")

if not all([KEYCLOAK_SERVER_URL, KEYCLOAK_REALM, KEYCLOAK_CLIENT_ID]):
    raise ValueError("Missing Keycloak configuration in environment variables.")

app = FastAPI()

from fastapi.middleware.cors import CORSMiddleware

# Initialize Keycloak middleware

keycloak_config = KeycloakConfiguration(realm=KEYCLOAK_REALM, 
                                        url=KEYCLOAK_SERVER_URL, 
                                        client_id=KEYCLOAK_CLIENT_ID,
                                        client_secret="oNwoLQdvJAvRcL89SydqCWCe5ry1jMgq",
                                        validate_token=True)
print(f"{keycloak_config=}")

app.add_middleware(KeycloakMiddleware, keycloak_configuration=keycloak_config)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow requests from this origin
    allow_credentials=True,
    allow_methods=["*"],  # Or specify only the needed HTTP methods
    allow_headers=["*"],  # Or specify only the needed headers
)


# Public endpoint
@app.get("/")
def read_root():
    return {"message": "Welcome to the secured FastAPI application!"}

# Secured endpoint
@app.get("/reports")
def read_reports(user: FastApiUser = Depends(get_user)):
    #if "prothetic_user" not in :
    #raise HTTPException(status_code=403, detail="Forbidden: Missing required role")

    print(f"{type(user)=}")
    print(f"{user.first_name=}")    #

    print(f"{user.__dict__=}") 

    if "Prothetic" not in user.first_name: # Я дико извиняюсь за вот это вот, но я уже все глаза выплакал - не могу получить роль пользователя
        raise HTTPException(status_code=403, detail="Forbidden: Missing required role")
    
    return {
        "message": "You are authorized to access reports."
    }