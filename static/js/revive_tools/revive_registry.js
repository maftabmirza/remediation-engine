/**
 * Client-Side Tool Registry for RE-VIVE
 * 
 * Manages registration and execution of JavaScript-based tools that can
 * extract page-specific context and interact with the DOM.
 */

class ClientToolRegistry {
    constructor() {
        this.tools = new Map();
        this.pendingRequests = new Map();
        this.debug = true; // Enable comprehensive debugging

        this.log('Registry initialized');
    }

    /**
     * Register a new client-side tool
     * @param {string} name - Tool name (must be unique)
     * @param {Object} definition - Tool definition
     */
    register(name, definition) {
        if (this.tools.has(name)) {
            this.warn(`Tool "${name}" is already registered, overwriting`);
        }

        // Validate definition
        if (!definition.handler || typeof definition.handler !== 'function') {
            throw new Error(`Tool "${name}" must have a handler function`);
        }

        this.tools.set(name, {
            name,
            description: definition.description || 'No description',
            parameters: definition.parameters || [],
            pageTypes: definition.pageTypes || null, // null = available on all pages
            handler: definition.handler,
            category: definition.category || 'general',
            requiresAuth: definition.requiresAuth !== false // Default true
        });

        this.log(`Registered tool: ${name}`, definition);
    }

    /**
     * Get all tools available for the current page type
     * @param {string} pageType - Current page type
     * @returns {Array} Available tools
     */
    getAvailableTools(pageType) {
        const available = Array.from(this.tools.entries())
            .filter(([name, tool]) => {
                // If no pageTypes specified, available everywhere
                if (!tool.pageTypes || tool.pageTypes.length === 0) {
                    return true;
                }
                // Check if current page type is in the allowed list
                return tool.pageTypes.includes(pageType);
            })
            .map(([name, tool]) => ({
                name: tool.name,
                type: 'client',
                description: tool.description,
                category: tool.category,
                parameters: tool.parameters,
                input_schema: this._buildInputSchema(tool)
            }));

        this.log(`Available tools for page "${pageType}": ${available.length}`, available.map(t => t.name));
        return available;
    }

    /**
     * Build Anthropic-compatible input schema
     */
    _buildInputSchema(tool) {
        const properties = {};
        const required = [];

        (tool.parameters || []).forEach(param => {
            properties[param.name] = {
                type: param.type || 'string',
                description: param.description || ''
            };
            if (param.enum) {
                properties[param.name].enum = param.enum;
            }
            if (param.required) {
                required.push(param.name);
            }
        });

        return {
            type: 'object',
            properties,
            required
        };
    }

    /**
     * Execute a client-side tool
     * @param {string} toolName - Name of tool to execute
     * @param {Object} args - Tool arguments
     * @returns {Promise<Object>} Tool result
     */
    async execute(toolName, args = {}) {
        const startTime = performance.now();
        this.log(`Executing tool: ${toolName}`, args);

        const tool = this.tools.get(toolName);
        if (!tool) {
            const error = `Tool "${toolName}" not found in registry`;
            this.error(error);
            throw new Error(error);
        }

        try {
            // Execute the tool handler
            const result = await tool.handler(args);

            const duration = Math.round(performance.now() - startTime);
            this.log(`Tool "${toolName}" completed in ${duration}ms`, result);

            return {
                success: true,
                tool_name: toolName,
                result,
                duration_ms: duration,
                timestamp: new Date().toISOString()
            };
        } catch (error) {
            const duration = Math.round(performance.now() - startTime);
            this.error(`Tool "${toolName}" failed after ${duration}ms:`, error);

            return {
                success: false,
                tool_name: toolName,
                error: error.message,
                error_stack: error.stack,
                duration_ms: duration,
                timestamp: new Date().toISOString()
            };
        }
    }

    /**
     * Handle tool execution request from backend
     * @param {Object} request - Tool execution request
     */
    async handleToolRequest(request) {
        const { tool_name, args, request_id } = request;

        this.log(`Received tool request:`, request);

        if (!request_id) {
            this.error('Tool request missing request_id');
            return null;
        }

        // Store request for tracking
        this.pendingRequests.set(request_id, {
            tool_name,
            args,
            started_at: Date.now()
        });

        try {
            const result = await this.execute(tool_name, args);
            this.pendingRequests.delete(request_id);
            return { request_id, ...result };
        } catch (error) {
            this.pendingRequests.delete(request_id);
            return {
                request_id,
                success: false,
                error: error.message
            };
        }
    }

    /**
     * Get current page type
     */
    detectPageType() {
        const path = window.location.pathname;

        if (path.includes('/runbooks')) return 'runbooks';
        if (path.includes('/alerts')) return 'alerts';
        if (path.includes('/panels')) return 'panels';
        if (path.includes('/knowledge')) return 'knowledge';
        if (path.includes('/dashboards')) return 'dashboards';
        if (path.includes('/grafana')) return 'grafana';
        if (path.includes('/prometheus')) return 'prometheus';

        return 'unknown';
    }

    // Logging utilities
    log(...args) {
        if (this.debug) {
            console.log('%c[ClientToolRegistry]', 'color: #4CAF50; font-weight: bold', ...args);
        }
    }

    warn(...args) {
        if (this.debug) {
            console.warn('%c[ClientToolRegistry]', 'color: #FF9800; font-weight: bold', ...args);
        }
    }

    error(...args) {
        console.error('%c[ClientToolRegistry]', 'color: #F44336; font-weight: bold', ...args);
    }
}

// Create global singleton
if (!window.reviveToolRegistry) {
    window.reviveToolRegistry = new ClientToolRegistry();
    console.log('%c[RE-VIVE] Client Tool Registry initialized', 'color: #2196F3; font-weight: bold; font-size: 14px');
}
