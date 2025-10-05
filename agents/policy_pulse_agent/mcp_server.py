# pip install googlemaps
import os
import googlemaps
from google.adk.agents import Agent
from google.adk.tools import FunctionTool  # ADK function tool
from modelcontextprotocol.server import Server
from modelcontextprotocol.tools import tool

@tool
gmaps = googlemaps.Client(key=os.environ["GOOGLE_MAPS_API_KEY"])

def get_directions(origin: str, destination: str, mode: str = "driving"):
    """Return Google Maps directions JSON between origin and destination."""
    # See parameters in official client docs
    return gmaps.directions(origin=origin, destination=destination, mode=mode)

maps_tool = FunctionTool.from_defaults(get_directions)

gmaps_directions_agent = Agent(
    name="maps_agent",
    model="gemini-1.5-pro",
    instruction="Use the get_directions tool for routing questions. Return concise steps.",
    tools=[maps_tool],
)

import os
from google.maps.addressvalidation_v1 import AddressValidationClient
from google.maps.addressvalidation_v1.types import ValidateAddressRequest, PostalAddress
from google.adk.tools.function_tools import FunctionTool

addr_client = AddressValidationClient()  # uses GOOGLE_API_KEY / ADC under the hood

@tool
def validate_address(
    region_code: str,
    postal_code: str | None = None,
    administrative_area: str | None = None,
    locality: str | None = None,
    address_lines: list[str] | None = None,
):
    """Validate and standardize a mailing address via Google Maps Address Validation."""
    address = PostalAddress(
        region_code=region_code,
        postal_code=postal_code or "",
        administrative_area=administrative_area or "",
        locality=locality or "",
        address_lines=address_lines or [],
    )
    """
    Example usage:

    addr = PostalAddress(
    region_code="GB",
    locality="London",            # UK post town
    postal_code="SE1 2LH",
    # administrative_area can be omitted; for GB it's often "England" or "Greater London"
    address_lines=["5 Copper Row"]
)
"""
    request = ValidateAddressRequest(address=address)
    resp = addr_client.validate_address(request=request)
    # Return a compact, LLM-friendly dict
    return {
        "formatted_address": resp.result.address.formatted_address,
        "validation_granularity": resp.result.verdict.validation_granularity.name,
        "geocode": {
            "location": getattr(resp.result.geocode.location, "to_dict", lambda: {})(),
            "plus_code": getattr(resp.result.geocode, "plus_code", None),
        },
        "address_components": [c.to_dict() for c in resp.result.address.address_components],
    }

address_tool = FunctionTool.from_defaults(validate_address)

addr_agent = Agent(
    name="address_validation_agent",
    model="gemini-1.5-pro",
    instruction="Validate and standardize addresses using the validate_address tool.",
    tools=[address_tool],
)

# --- Run the MCP server ---
if __name__ == "__main__":
    server = Server("maps-mcp")
    server.add_tool(get_directions)
    server.add_tool(validate_address)
    server.run()