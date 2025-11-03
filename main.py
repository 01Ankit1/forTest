from fastmcp import FastMCP,Context
import os
import tempfile

from fastmcp import FastMCP, Context
from scalekit import ScalekitClient
from scalekit.common.scalekit import TokenValidationOptions
from fastapi import HTTPException
import os
import tempfile

# Initialize MCP app
mcp = FastMCP("ExpenseTracker")

# Initialize Scalekit client
_scalekit_client = ScalekitClient(
    "https://paytm.scalekit.dev",
    "m2m_97422068261325572",
    "test_8c5ODRZ6DCsNzOdVSRSxrVja3ccDGdAAQlgbOybPqfAVzBvhngce3NiUNuEssLAQ"

)


@mcp.tool()
async def addNumber(a,b,ctx: Context = None)->int:
    "this will add a number"
    await validate_request_token(ctx)

    return a + b+10

@mcp.tool()
async def tellMeData(ctx: Context = None)->int:
    "this will tell date"
    await validate_request_token(ctx)
    return 10

@mcp.tool()
async def whatISThePSyco(ctx: Context = None)->int:
    "this will tell date"
    await validate_request_token(ctx)
    return 10

@mcp.custom_route("/.well-known/oauth-protected-resource/mcp")
async def oauth_protected_resource_metadata():
    """
    OAuth 2.0 Protected Resource Metadata endpoint for MCP client discovery.
    Required by the MCP specification for authorization server discovery.
    """

    return {"authorization_servers":["https://paytm.scalekit.dev/resources/res_97420808191740418"],"bearer_methods_supported":["header"],"resource":"https://forTest.fastmcp.app/mcp","resource_documentation":"https://forTest.fastmcp.app/mcp/docs","scopes_supported":["user:read","user:write"]}

async def validate_request_token(ctx: Context):
    """
    Extracts and validates the Bearer token from the context headers.
    Raises HTTPException if invalid or missing.
    """
    auth_header = ctx.headers.get("authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    token = auth_header.split("Bearer ")[1].strip()

    validation_options = TokenValidationOptions(
        verify_signature=True,
        verify_exp=True,
        verify_aud=True
    )

    try:
        _scalekit_client.validate_token(token, options=validation_options)
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Token validation failed: {str(e)}")

    return True

# Start the server
if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=8001)
