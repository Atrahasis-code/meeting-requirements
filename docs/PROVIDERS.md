# Local providers

Available providers are ChatGPT through official application-owned OAuth and explicit Mock for offline tests. Each installation keeps its own authentication and usage controls; it never uses another operator's account.

The provider interface is separate from processing and data. Adding a provider requires authentication officially permitted for third-party applications, credential isolation, per-input consent, structural and evidence validation, credential-free tests, and a separate authorized real check.

Claude and Grok are not shown as available OAuth connections. Tokens are not extracted from their applications, and a chat subscription is not assumed to provide API access. Automatic switching to key-based billing is not implemented.

Review the provider's current terms before adding an integration. Reference documentation: [OpenAI](https://developers.openai.com/siwc/token-sharing-open-source), [Anthropic](https://code.claude.com/docs/en/legal-and-compliance), [xAI](https://docs.x.ai/developers/quickstart).
