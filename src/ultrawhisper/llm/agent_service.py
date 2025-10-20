#!/usr/bin/env python3
"""
OpenAI Agent Service - Uses OpenAI's agents SDK for enhanced question mode responses.

This service provides agent-based conversations with tools like web search
for more intelligent and context-aware responses in question mode.
"""

import time
from typing import Dict, Any, Optional, Union
from loguru import logger

# Import agents SDK
try:
    from agents import Agent, Runner, SQLiteSession, WebSearchTool, set_default_openai_key
    from agents.mcp import MCPServerStdio
    import asyncio
    AGENTS_AVAILABLE = True
except ImportError:
    AGENTS_AVAILABLE = False

from ultrawhisper.logging_config import LogHelper


class AgentServiceException(Exception):
    """Exception raised for errors in the Agent Service."""
    pass


class OpenAIAgentService:
    """
    OpenAI Agent service for enhanced question mode responses.

    Uses the OpenAI agents SDK to provide intelligent responses with tools
    like web search capabilities.
    """

    def __init__(self, full_config: Any):
        """
        Initialize the agent service.

        Args:
            full_config: Full application configuration (UltraWhisperConfig Pydantic model)
        """
        self.full_config = full_config

        # Extract question mode prompt from config
        self.question_prompt = self._get_question_prompt()
        self.provider = full_config.llm.provider
        self.model = full_config.llm.model
        self.api_key = full_config.llm.api_key
        self.skip_if_unavailable = full_config.llm.skip_if_unavailable

        # Agent and session
        self.agent = None
        self.current_session = None
        self.session_id = "ultrawhisper_session"

        # MCP servers
        self.mcp_servers = []
        self.mcp_server_contexts = []  # Store context managers for cleanup
        self.mcp_server_status = {}  # Track MCP server connection status
        self.mcp_event_loop = None  # Event loop running in background thread
        self.mcp_loop_thread = None  # Background thread for MCP event loop

        logger.info(f"🤖 Agent Service Configuration:")
        logger.info(f"  Provider: {self.provider}")
        logger.info(f"  Model: {self.model}")
        logger.info(f"  API Key: {'***' if self.api_key else 'None'}")
        logger.info(f"  Agents SDK Available: {AGENTS_AVAILABLE}")

        # Check for MCP servers in config
        mcp_configs = full_config.llm.mcp_servers if full_config.llm.mcp_servers else []
        if mcp_configs:
            logger.info(f"  MCP Servers: {len(mcp_configs)} configured")

        # Initialize agent if possible
        self._initialize_agent()

    def _get_question_prompt(self) -> str:
        """
        Extract question mode prompt from configuration.

        Returns:
            Question mode prompt string
        """
        if not self.full_config:
            return (
                "You are UltraWhisper's AI assistant. You help users by answering questions "
                "with accurate, concise information. You can search the web for current information "
                "when needed. Be helpful, direct, and context-aware."
            )

        # Handle both Pydantic model and dict config
        try:
            # Try Pydantic model first
            if hasattr(self.full_config, 'modes'):
                prompt = self.full_config.modes.question.context_prompts.get('default', '')
                if prompt:
                    return prompt

            # Fallback to dict access
            config_dict = self.full_config
            if hasattr(self.full_config, 'model_dump'):
                config_dict = self.full_config.model_dump()

            modes_config = config_dict.get('modes', {})
            question_config = modes_config.get('question', {})
            context_prompts = question_config.get('context_prompts', {})
            prompt = context_prompts.get('default', '')

            if prompt:
                return prompt

        except Exception as e:
            logger.warning(f"Error extracting question prompt from config: {e}")

        # Default fallback
        return (
            "You are UltraWhisper's AI assistant. You help users by answering questions "
            "with accurate, concise information. You can search the web for current information "
            "when needed. Be helpful, direct, and context-aware."
        )

    def _initialize_mcp_servers_sync(self) -> None:
        """Initialize MCP servers synchronously (wrapper for async initialization)."""
        import threading

        # Always create a dedicated event loop in a background thread for MCP servers
        # This keeps the MCP connections alive
        init_complete = threading.Event()

        def run_mcp_loop():
            """Run event loop in background thread to keep MCP servers alive."""
            # Create a new event loop for this thread
            self.mcp_event_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.mcp_event_loop)

            try:
                # Initialize MCP servers
                self.mcp_event_loop.run_until_complete(self._initialize_mcp_servers_async())
                init_complete.set()  # Signal initialization complete

                # Keep the loop running to maintain MCP connections
                self.mcp_event_loop.run_forever()
            except Exception as e:
                logger.error(f"🤖 MCP event loop error: {e}")
                init_complete.set()
            finally:
                self.mcp_event_loop.close()

        self.mcp_loop_thread = threading.Thread(target=run_mcp_loop, daemon=True)
        self.mcp_loop_thread.start()

        # Wait for initialization to complete
        init_complete.wait(timeout=10)  # 10 second timeout

    async def _initialize_mcp_servers_async(self) -> None:
        """Initialize MCP servers asynchronously."""
        # Access Pydantic model attributes directly
        mcp_configs = self.full_config.llm.mcp_servers if self.full_config.llm.mcp_servers else []

        if not mcp_configs:
            logger.debug("🤖 No MCP servers configured")
            return

        import os

        for mcp_config in mcp_configs:
            try:
                server_name = mcp_config.name
                command = mcp_config.command
                args = mcp_config.args if mcp_config.args else []
                env = mcp_config.env if mcp_config.env else None

                logger.info(f"🤖 Initializing MCP server: {server_name}")
                logger.debug(f"🤖   Command: {command}")
                logger.debug(f"🤖   Args: {args}")

                # Merge env with os.environ if provided
                if env:
                    server_env = {**os.environ, **env}
                else:
                    server_env = dict(os.environ)

                # Suppress MCP server logging to avoid polluting TUI
                # Set various logging environment variables that MCP servers might use
                server_env["PYTHONUNBUFFERED"] = "1"
                # Common logging env vars
                for log_var in ["LOGLEVEL", "LOG_LEVEL", "FASTMCP_LOG_LEVEL"]:
                    if log_var not in server_env:
                        server_env[log_var] = "ERROR"
                # Disable INFO logging from common libraries
                server_env["HTTPX_LOG_LEVEL"] = "WARNING"
                server_env["MCP_LOG_LEVEL"] = "WARNING"

                # Create MCP server with stdio transport
                # Set a long timeout for slow operations like image generation (5 minutes)
                server = MCPServerStdio(
                    cache_tools_list=True,
                    client_session_timeout_seconds=300,  # 5 minutes for slow operations
                    params={
                        "command": command,
                        "args": args,
                        "env": server_env,
                    },
                )

                # Enter the async context manager and store both the context and the result
                # We keep the context manager open by not calling __aexit__
                server_instance = await server.__aenter__()
                self.mcp_servers.append(server_instance)
                self.mcp_server_contexts.append((server, server_instance))

                # Mark as connected (we'll update this based on actual connection status)
                self.mcp_server_status[server_name] = {
                    "connected": True,
                    "name": server_name,
                    "command": command,
                    "tool_count": 0,  # Will be updated after agent initialization
                }

                logger.info(f"🤖 MCP server '{server_name}' initialized successfully")

            except Exception as e:
                import traceback
                error_msg = str(e) if str(e) else repr(e)
                logger.error(f"🤖 Failed to initialize MCP server '{server_name}': {error_msg}")
                logger.debug(f"🤖 MCP server error traceback:\n{traceback.format_exc()}")
                self.mcp_server_status[server_name] = {
                    "connected": False,
                    "name": server_name,
                    "error": error_msg,
                }

    def _initialize_agent(self) -> None:
        """Initialize the OpenAI agent with tools and MCP servers."""
        if not AGENTS_AVAILABLE:
            logger.warning("🤖 Agents SDK not available - agent service disabled")
            return

        if self.provider != "openai":
            logger.warning(f"🤖 Agent service only supports OpenAI provider, got {self.provider}")
            return

        if not self.api_key:
            logger.warning("🤖 No OpenAI API key provided - agent service disabled")
            return

        try:
            # Set the OpenAI API key for the agents SDK
            set_default_openai_key(self.api_key)

            # Initialize MCP servers if configured
            self._initialize_mcp_servers_sync()

            # Create agent with web search capability using configured prompt
            agent_instructions = f"{self.question_prompt} You can search the web for current information when needed. When referring to previous parts of the conversation, acknowledge the context naturally."

            # Build agent kwargs
            agent_kwargs = {
                "name": "UltraWhisper Assistant",
                "instructions": agent_instructions,
                "model": self.model,
                "tools": [WebSearchTool()],
            }

            # Only add mcp_servers if we have any
            if self.mcp_servers:
                agent_kwargs["mcp_servers"] = self.mcp_servers

            self.agent = Agent(**agent_kwargs)

            logger.info("🤖 OpenAI Agent initialized successfully with web search tool")
            if self.mcp_servers:
                logger.info(f"🤖 Agent configured with {len(self.mcp_servers)} MCP server(s)")
            LogHelper.service_status("Agent Service", "initialized", f"Agent with {self.model}")

        except Exception as e:
            logger.error(f"🤖 Failed to initialize agent: {e}")
            self.agent = None
            if not self.skip_if_unavailable:
                raise AgentServiceException(f"Failed to initialize agent: {e}")

    def is_available(self) -> bool:
        """Check if the agent service is available."""
        return (
            AGENTS_AVAILABLE and
            self.provider == "openai" and
            self.api_key and
            self.agent is not None
        )

    def create_new_session(self) -> bool:
        """
        Create a new agent session.

        Returns:
            True if session created successfully, False otherwise
        """
        if not self.is_available():
            logger.warning("🤖 Agent service not available - cannot create session")
            return False

        try:
            # Use in-memory SQLite session
            self.current_session = SQLiteSession(self.session_id)
            logger.info("🤖 New agent session created")
            return True

        except Exception as e:
            logger.error(f"🤖 Failed to create agent session: {e}")
            self.current_session = None
            return False

    def get_response(self, question: str, context: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """
        Get a response from the agent for the given question.

        Args:
            question: User's question
            context: Optional application context

        Returns:
            Agent's response as string, or None if failed
        """
        if not self.is_available():
            logger.warning("🤖 Agent service not available")
            return None

        if not self.current_session:
            logger.info("🤖 No active session, creating new one")
            if not self.create_new_session():
                return None

        # Add context information to the question if available
        enhanced_question = question
        if context and context.get('app'):
            app_name = context['app']
            enhanced_question = f"[Context: User is in {app_name}] {question}"

        logger.info(f"🤖 Agent processing question: {enhanced_question[:200]}{'...' if len(enhanced_question) > 200 else ''}")

        # Log the request
        LogHelper.llm_request("openai-agent", self.model, "agents-api", len(enhanced_question))

        try:
            start_time = time.time()

            # Get response from agent using Runner.run
            # If we have MCP servers, run on their event loop; otherwise create a new one
            if self.mcp_event_loop and self.mcp_event_loop.is_running():
                # Run on MCP event loop to maintain connection
                future = asyncio.run_coroutine_threadsafe(
                    Runner.run(self.agent, enhanced_question, session=self.current_session),
                    self.mcp_event_loop
                )
                response = future.result(timeout=60)  # 60 second timeout
            else:
                # No MCP servers, run normally
                response = asyncio.run(Runner.run(
                    self.agent,
                    enhanced_question,
                    session=self.current_session
                ))

            duration = time.time() - start_time
            final_output = response.final_output

            logger.info(f"🤖 Agent response: {final_output[:200]}{'...' if len(final_output) > 200 else ''}")
            LogHelper.llm_response(final_output, duration, {})

            return final_output

        except Exception as e:
            import traceback
            error_msg = str(e) if str(e) else repr(e)
            logger.error(f"🤖 Agent error: {error_msg}")
            logger.error(f"🤖 Agent error traceback:\n{traceback.format_exc()}")
            LogHelper.llm_error("openai-agent", error_msg)

            if self.skip_if_unavailable:
                return None
            else:
                raise AgentServiceException(f"Agent error: {error_msg}")

    def clear_session(self) -> None:
        """Clear the current session to start fresh."""
        if self.current_session:
            logger.info("🤖 Clearing agent session")
            self.current_session = None

    def get_mcp_status(self) -> Dict[str, Any]:
        """
        Get the status of all MCP servers.

        Returns:
            Dictionary with MCP server statuses
        """
        return {
            "servers": list(self.mcp_server_status.values()),
            "total": len(self.mcp_server_status),
            "connected": sum(1 for s in self.mcp_server_status.values() if s.get("connected", False)),
        }

    def cleanup(self) -> None:
        """Clean up agent service resources."""
        if self.mcp_server_contexts:
            logger.info("🤖 Cleaning up MCP servers")
            try:
                # Schedule cleanup on the MCP event loop
                if self.mcp_event_loop and self.mcp_event_loop.is_running():
                    # Schedule cleanup coroutine
                    asyncio.run_coroutine_threadsafe(
                        self._cleanup_mcp_servers_async(),
                        self.mcp_event_loop
                    ).result(timeout=5)

                    # Stop the event loop
                    self.mcp_event_loop.call_soon_threadsafe(self.mcp_event_loop.stop)

                # Wait for thread to finish
                if self.mcp_loop_thread and self.mcp_loop_thread.is_alive():
                    self.mcp_loop_thread.join(timeout=2)

            except Exception as e:
                logger.error(f"🤖 Error during MCP cleanup: {e}")

    async def _cleanup_mcp_servers_async(self) -> None:
        """Clean up MCP server connections (async)."""
        for server, server_instance in self.mcp_server_contexts:
            try:
                await server.__aexit__(None, None, None)
            except Exception as e:
                logger.error(f"🤖 Error cleaning up MCP server: {e}")

        self.mcp_servers.clear()
        self.mcp_server_contexts.clear()
        self.mcp_server_status.clear()

    def get_session_info(self) -> Dict[str, Any]:
        """
        Get information about the current session.

        Returns:
            Dictionary with session information
        """
        return {
            "available": self.is_available(),
            "has_session": self.current_session is not None,
            "agent_name": self.agent.name if self.agent else None,
            "model": self.model,
            "provider": self.provider,
        }

    def test_connection(self) -> Dict[str, Any]:
        """
        Test the agent service with a simple question.

        Returns:
            Dictionary with test results
        """
        test_question = "What is 2 + 2?"

        try:
            if not self.is_available():
                return {
                    "success": False,
                    "provider": "openai-agent",
                    "error": "Agent service not available",
                }

            # Create a temporary session for testing
            if not self.current_session:
                if not self.create_new_session():
                    return {
                        "success": False,
                        "provider": "openai-agent",
                        "error": "Could not create test session",
                    }

            response = self.get_response(test_question)

            return {
                "success": response is not None,
                "provider": "openai-agent",
                "model": self.model,
                "test_input": test_question,
                "test_output": response or "No response",
            }

        except Exception as e:
            return {
                "success": False,
                "provider": "openai-agent",
                "model": self.model,
                "error": str(e),
            }


def create_agent_service(config: Any) -> OpenAIAgentService:
    """Create an agent service instance from configuration."""
    return OpenAIAgentService(config)


# CLI for testing
if __name__ == "__main__":
    import argparse
    import os

    def main():
        parser = argparse.ArgumentParser(description="Test OpenAI Agent Service")
        parser.add_argument("--api-key", help="OpenAI API key")
        parser.add_argument("--model", default="gpt-4o", help="Model name")
        parser.add_argument("--question", default="What's the weather like today?", help="Test question")

        args = parser.parse_args()

        # Configure logging
        import logging
        logging.basicConfig(level=logging.INFO)

        # Create config
        config = {
            "llm": {
                "provider": "openai",
                "model": args.model,
                "api_key": args.api_key or os.getenv("OPENAI_API_KEY", ""),
                "skip_if_unavailable": False,
            }
        }

        # Test the service
        service = create_agent_service(config)

        print(f"Testing OpenAI Agent Service with model {args.model}")
        print(f"Question: {args.question}")

        # Test connection
        test_result = service.test_connection()
        if test_result["success"]:
            print("✓ Agent service test successful")
            print(f"Response: {test_result['test_output']}")
        else:
            print(f"✗ Agent service test failed: {test_result.get('error', 'Unknown error')}")

    main()