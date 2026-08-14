"""
odoo_mcp_foundry_connector.py

Purpose:
  A minimal, standalone script whose ONLY job is to connect your Foundry
  agent to your locally-hosted Odoo MCP server (exposed via a Cloudflare
  tunnel) and run a single test query through it.

  This is a CONNECTOR/TEST script, not a full agent app. Use it to verify
  end-to-end plumbing before building anything more complex on top.

Prerequisites (must already be true before running this):
  1. odoo-mcp-server.py is running locally in HTTP mode:
         uv run python odoo-mcp-server.py --http
  2. A Cloudflare tunnel is pointed at it:
         cloudflared tunnel --url http://localhost:8000
     -> copy the https://xxxx.trycloudflare.com URL it prints.
  3. You are logged into Azure CLI (az login) so DefaultAzureCredential works.
  4. Your .env file has:
         PROJECT_ENDPOINT=<your Foundry project endpoint>
         MODEL_DEPLOYMENT=<your model deployment name, e.g. gpt-4.1-mini>
         MCP_SERVER_URL=<your Cloudflare URL + /mcp>

Dependencies:
  pip install azure-ai-projects azure-identity python-dotenv
  (openai client comes bundled via project_client.get_openai_client())
"""

import os
import sys
from dotenv import load_dotenv
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import MCPTool


def main():
    os.system("cls" if os.name == "nt" else "clear")
    load_dotenv()

    project_endpoint = os.getenv("PROJECT_ENDPOINT")
    model_deployment = os.getenv("MODEL_DEPLOYMENT")
    mcp_server_url = os.getenv("MCP_SERVER_URL")  # e.g. https://xxxx.trycloudflare.com/mcp

    # --- Fail fast with clear errors instead of cryptic SDK exceptions ---
    missing = [
        name
        for name, val in [
            ("PROJECT_ENDPOINT", project_endpoint),
            ("MODEL_DEPLOYMENT", model_deployment),
            ("MCP_SERVER_URL", mcp_server_url),
        ]
        if not val
    ]
    if missing:
        print(f"ERROR: Missing required .env values: {', '.join(missing)}")
        sys.exit(1)

    with (
        DefaultAzureCredential() as credential,
        AIProjectClient(endpoint=project_endpoint, credential=credential) as project_client,
        project_client.get_openai_client() as openai_client,
    ):
        # MCP tool pointing at YOUR Odoo server, tunneled through Cloudflare.
        # - server_label: your own name for the server, shown in tool-call logs
        # - server_url: the public Cloudflare URL to your /mcp endpoint
        # - require_approval: "never" for fast local testing.
        #   Switch to "always" once you move toward production, so you can
        #   review/approve each tool call before it executes.
        mcp_tool = MCPTool(
            server_label="odoo-crm",
            server_url=mcp_server_url,
            require_approval="never",
        )

        print(f"Connecting agent to MCP server: {mcp_server_url}")
        print(f"Using model deployment: {model_deployment}\n")

        # Single test call through the Responses API with the MCP tool attached.
        # The model decides on its own whether/which Odoo tool to call.
        response = openai_client.responses.create(
            model=model_deployment,
            input="Find stalled opportunities over $50,000, cross-reference with accounts needing attention, and tell me which 2 I should call this week and why. show the used tool calls in the output.",
            tools=[mcp_tool],
        )

        print("=== Agent Response ===")
        print(response.output_text)


if __name__ == "__main__":
    main()
