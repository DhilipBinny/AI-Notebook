-- Migration 006: Create llm_models table (replaces llm_pricing)
-- This migration creates a unified model registry combining identity, capabilities, and pricing.

-- Step 1: Create the llm_models table
CREATE TABLE IF NOT EXISTS llm_models (
    id INT NOT NULL AUTO_INCREMENT,
    provider VARCHAR(50) NOT NULL,
    model_id VARCHAR(100) NOT NULL,
    display_name VARCHAR(150) NOT NULL,

    -- Capabilities
    context_window INT NULL,
    max_output_tokens INT NULL,
    supports_vision TINYINT(1) NOT NULL DEFAULT 0,
    supports_function_calling TINYINT(1) NOT NULL DEFAULT 0,
    supports_streaming TINYINT(1) NOT NULL DEFAULT 1,

    -- Pricing (cents per 1M tokens)
    input_cost_per_1m_cents INT NOT NULL DEFAULT 0,
    output_cost_per_1m_cents INT NOT NULL DEFAULT 0,
    margin_multiplier DECIMAL(3,2) NOT NULL DEFAULT 1.30,

    -- Status
    is_active TINYINT(1) NOT NULL DEFAULT 1,
    is_custom TINYINT(1) NOT NULL DEFAULT 0,
    sort_order INT NOT NULL DEFAULT 0,

    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (id),
    UNIQUE KEY uk_llm_models_provider_model (provider, model_id),
    INDEX idx_llm_models_active (is_active),
    INDEX idx_llm_models_provider (provider)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- Step 2: Migrate existing data from llm_pricing
INSERT INTO llm_models (provider, model_id, display_name, input_cost_per_1m_cents, output_cost_per_1m_cents, margin_multiplier, is_active)
SELECT provider, model, model, input_cost_per_1m_cents, output_cost_per_1m_cents, margin_multiplier, is_active
FROM llm_pricing
ON DUPLICATE KEY UPDATE
    input_cost_per_1m_cents = VALUES(input_cost_per_1m_cents),
    output_cost_per_1m_cents = VALUES(output_cost_per_1m_cents),
    margin_multiplier = VALUES(margin_multiplier);


-- Step 3: Update display names
UPDATE llm_models SET display_name = 'GPT-4o' WHERE provider = 'openai' AND model_id = 'gpt-4o';
UPDATE llm_models SET display_name = 'GPT-4o Mini' WHERE provider = 'openai' AND model_id = 'gpt-4o-mini';
UPDATE llm_models SET display_name = 'GPT-4.1' WHERE provider = 'openai' AND model_id = 'gpt-4.1';
UPDATE llm_models SET display_name = 'GPT-4.1 Mini' WHERE provider = 'openai' AND model_id = 'gpt-4.1-mini';
UPDATE llm_models SET display_name = 'GPT-4.1 Nano' WHERE provider = 'openai' AND model_id = 'gpt-4.1-nano';
UPDATE llm_models SET display_name = 'o3-mini' WHERE provider = 'openai' AND model_id = 'o3-mini';
UPDATE llm_models SET display_name = 'Claude Sonnet 4' WHERE provider = 'anthropic' AND model_id = 'claude-sonnet-4-20250514';
UPDATE llm_models SET display_name = 'Claude Haiku 4.5' WHERE provider = 'anthropic' AND model_id = 'claude-haiku-4-5-20251001';
UPDATE llm_models SET display_name = 'Claude 3.5 Sonnet' WHERE provider = 'anthropic' AND model_id = 'claude-3-5-sonnet-20241022';
UPDATE llm_models SET display_name = 'Gemini 2.0 Flash' WHERE provider = 'gemini' AND model_id = 'gemini-2.0-flash';
UPDATE llm_models SET display_name = 'Gemini 2.0 Flash Lite' WHERE provider = 'gemini' AND model_id = 'gemini-2.0-flash-lite';
UPDATE llm_models SET display_name = 'Gemini 2.5 Pro' WHERE provider = 'gemini' AND model_id = 'gemini-2.5-pro';
UPDATE llm_models SET display_name = 'Gemini 2.5 Flash' WHERE provider = 'gemini' AND model_id = 'gemini-2.5-flash';
UPDATE llm_models SET display_name = 'Custom Model' WHERE provider = 'openai_compatible' AND model_id = 'custom';


-- Step 4: Update capabilities
-- OpenAI models
UPDATE llm_models SET context_window = 128000, max_output_tokens = 16384, supports_vision = TRUE, supports_function_calling = TRUE, sort_order = 1 WHERE provider = 'openai' AND model_id = 'gpt-4o';
UPDATE llm_models SET context_window = 128000, max_output_tokens = 16384, supports_vision = TRUE, supports_function_calling = TRUE, sort_order = 2 WHERE provider = 'openai' AND model_id = 'gpt-4o-mini';
UPDATE llm_models SET context_window = 1047576, max_output_tokens = 32768, supports_vision = TRUE, supports_function_calling = TRUE, sort_order = 3 WHERE provider = 'openai' AND model_id = 'gpt-4.1';
UPDATE llm_models SET context_window = 1047576, max_output_tokens = 32768, supports_vision = TRUE, supports_function_calling = TRUE, sort_order = 4 WHERE provider = 'openai' AND model_id = 'gpt-4.1-mini';
UPDATE llm_models SET context_window = 1047576, max_output_tokens = 32768, supports_vision = FALSE, supports_function_calling = TRUE, sort_order = 5 WHERE provider = 'openai' AND model_id = 'gpt-4.1-nano';
UPDATE llm_models SET context_window = 200000, max_output_tokens = 100000, supports_vision = FALSE, supports_function_calling = TRUE, sort_order = 6 WHERE provider = 'openai' AND model_id = 'o3-mini';

-- Anthropic models
UPDATE llm_models SET context_window = 200000, max_output_tokens = 16000, supports_vision = TRUE, supports_function_calling = TRUE, sort_order = 1 WHERE provider = 'anthropic' AND model_id = 'claude-sonnet-4-20250514';
UPDATE llm_models SET context_window = 200000, max_output_tokens = 8192, supports_vision = TRUE, supports_function_calling = TRUE, sort_order = 2 WHERE provider = 'anthropic' AND model_id = 'claude-haiku-4-5-20251001';
UPDATE llm_models SET context_window = 200000, max_output_tokens = 8192, supports_vision = TRUE, supports_function_calling = TRUE, sort_order = 3 WHERE provider = 'anthropic' AND model_id = 'claude-3-5-sonnet-20241022';

-- Gemini models
UPDATE llm_models SET context_window = 1048576, max_output_tokens = 8192, supports_vision = TRUE, supports_function_calling = TRUE, sort_order = 1 WHERE provider = 'gemini' AND model_id = 'gemini-2.0-flash';
UPDATE llm_models SET context_window = 1048576, max_output_tokens = 8192, supports_vision = TRUE, supports_function_calling = TRUE, sort_order = 2 WHERE provider = 'gemini' AND model_id = 'gemini-2.0-flash-lite';
UPDATE llm_models SET context_window = 1048576, max_output_tokens = 65536, supports_vision = TRUE, supports_function_calling = TRUE, sort_order = 3 WHERE provider = 'gemini' AND model_id = 'gemini-2.5-pro';
UPDATE llm_models SET context_window = 1048576, max_output_tokens = 65536, supports_vision = TRUE, supports_function_calling = TRUE, sort_order = 4 WHERE provider = 'gemini' AND model_id = 'gemini-2.5-flash';

-- OpenAI Compatible (custom) - no capabilities set, custom models vary
UPDATE llm_models SET is_custom = FALSE, sort_order = 99 WHERE provider = 'openai_compatible' AND model_id = 'custom';


-- Step 5: Backfill any platform key models not in the registry
INSERT IGNORE INTO llm_models (provider, model_id, display_name, is_custom, margin_multiplier)
SELECT DISTINCT provider, model_name, model_name, TRUE, 1.00
FROM platform_api_keys
WHERE model_name IS NOT NULL
AND model_name != ''
AND NOT EXISTS (
    SELECT 1 FROM llm_models WHERE llm_models.provider COLLATE utf8mb4_unicode_ci = platform_api_keys.provider AND llm_models.model_id COLLATE utf8mb4_unicode_ci = platform_api_keys.model_name
);


-- After verifying everything works:
-- DROP TABLE llm_pricing;
