from fastmcp import FastMCP
import os
import tempfile



mcp = FastMCP("ExpenseTracker")


@mcp.tool()
async def addNumber(a,b)->int:
    "this will add a number"
    return a + b+10

@mcp.tool()
async def tellMeData()->int:
    "this will tell date"
    return 10


# Start the server
if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=8001)
