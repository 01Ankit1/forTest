import json
import uvicorn
import logging
import time
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer
from starlette.middleware.base import BaseHTTPMiddleware

from fastmcp import FastMCP, Context
from scalekit import ScalekitClient
from scalekit.common.scalekit import TokenValidationOptions

# --- LOGGER SETUP ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)
logger = logging.getLogger("middleware_logger")

# ---  FASTMCP INSTANCE  ---
mcp = FastMCP("ExpenseTracker")

# ---  PUBLIC FASTAPI APP FOR WELL-KNOWN ENDPOINTS  ---
public_app = FastAPI()
security = HTTPBearer()


@public_app.get("/.well-known/oauth-protected-resource/mcp")
async def oauth_protected_resource_metadata():
    """Public metadata endpoint (no auth required)."""
    logger.info("[PUBLIC] Metadata endpoint hit.")
    data = {
        "authorization_servers": [
            "https://paytm.scalekit.dev/resources/res_97420808191740418"
        ],
        "bearer_methods_supported": ["header"],
        "resource": "https://forTest.fastmcp.app/mcp",
        "resource_documentation": "https://forTest.fastmcp.app/mcp/docs",
        "scopes_supported": ["user:read", "user:write"],
    }
    logger.info("[PUBLIC] Returning metadata response.")
    return JSONResponse(content=data)


# ---  SCALEKIT CLIENT  ---
_scalekit_client = ScalekitClient(
    "https://paytm.scalekit.dev",
    "m2m_97422068261325572",
    "test_8c5ODRZ6DCsNzOdVSRSxrVja3ccDGdAAQlgbOybPqfAVzBvhngce3NiUNuEssLAQ",
)


# ---  SETTINGS  ---
class Settings:
    SCALEKIT_ENVIRONMENT_URL = "https://paytm.scalekit.dev"
    SCALEKIT_AUDIENCE_NAME = "https://forTest.fastmcp.app/mcp"
    SCALEKIT_RESOURCE_METADATA_URL = (
        "https://forTest.fastmcp.app/.well-known/oauth-protected-resource/mcp"
    )


settings = Settings()


# ---  AUTH MIDDLEWARE WITH LOGGING  ---
class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        logger.info(f"[AUTH-MW] Incoming request: {request.method} {request.url.path}")

        # Skip auth for well-known endpoints
        if request.url.path.startswith("/.well-known/"):
            logger.info("[AUTH-MW] Skipping auth for well-known path.")
            return await call_next(request)

        try:
            auth_header = request.headers.get("Authorization")
            if not auth_header or not auth_header.startswith("Bearer "):
                logger.warning("[AUTH-MW] Missing or invalid Authorization header.")
                raise HTTPException(
                    status_code=401, detail="Missing or invalid authorization header"
                )

            token = auth_header.split(" ")[1]
            body_bytes = await request.body()

            # Parse request JSON safely
            try:
                request_data = json.loads(body_bytes.decode("utf-8")) if body_bytes else {}
                logger.info(f"[AUTH-MW] Parsed request body: {request_data}")
            except (json.JSONDecodeError, UnicodeDecodeError):
                request_data = {}
                logger.warning("[AUTH-MW] Failed to parse JSON body.")

            validation_options = TokenValidationOptions(
                issuer=settings.SCALEKIT_ENVIRONMENT_URL,
                audience=[settings.SCALEKIT_AUDIENCE_NAME],
            )

            is_tool_call = request_data.get("method") == "tools/call"
            if is_tool_call:
                logger.info("[AUTH-MW] Detected tool call; requiring 'search:read' scope.")
                validation_options.required_scopes = ["search:read"]

            # Validate the token
            logger.info("[AUTH-MW] Validating token...")
            _scalekit_client.validate_token(token, options=validation_options)
            logger.info("[AUTH-MW] Token validated successfully.")

        except HTTPException as e:
            logger.error(f"[AUTH-MW] Auth failed: {e.detail}")
            return JSONResponse(
                status_code=e.status_code,
                content={
                    "error": "unauthorized" if e.status_code == 401 else "forbidden",
                    "error_description": e.detail,
                },
                headers={
                    "WWW-Authenticate": (
                        f'Bearer realm="OAuth", '
                        f'resource_metadata="{settings.SCALEKIT_RESOURCE_METADATA_URL}"'
                    )
                },
            )
        except Exception as ex:
            logger.exception(f"[AUTH-MW] Unexpected error: {ex}")
            return JSONResponse(
                status_code=500,
                content={"error": "server_error", "error_description": str(ex)},
            )

        response = await call_next(request)
        process_time = (time.time() - start_time) * 1000
        logger.info(f"[AUTH-MW] Completed in {process_time:.2f} ms with status {response.status_code}")
        return response


# ---  MCP TOOLS WITH LOGGING  ---
@mcp.tool()
async def addNumber(a: int, b: int, ctx: Context = None) -> int:
    logger.info(f"[TOOL:addNumber] Called with a={a}, b={b}")
    result = a + b + 10
    logger.info(f"[TOOL:addNumber] Returning result={result}")
    return result


@mcp.tool()
async def tellMeData(ctx: Context = None) -> int:
    logger.info("[TOOL:tellMeData] Called")
    return 10


@mcp.tool()
async def whatISThePSyco(ctx: Context = None) -> int:
    logger.info("[TOOL:whatISThePSyco] Called")
    return 10


# ---  COMBINE BOTH ASGI APPS  ---
combined = FastAPI()

mcp_app = mcp.http_app()
combined.add_middleware(AuthMiddleware)
combined.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # NOTE: Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

combined.mount("/mcp", mcp_app)
combined.mount("", public_app)


# ---  STARTUP / SHUTDOWN LOGGING  ---
@combined.on_event("startup")
async def startup_event():
    logger.info("[SYSTEM] Application startup complete.")


@combined.on_event("shutdown")
async def shutdown_event():
    logger.info("[SYSTEM] Application shutdown initiated.")


# ---  MAIN ENTRY POINT  ---
if __name__ == "__main__":
    logger.info("[SYSTEM] Starting server on port 8002...")
    uvicorn.run(combined, host="0.0.0.0", port=8002)
