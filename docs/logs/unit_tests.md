# Unit test run

- Command: `uv run pytest -v` in each service folder (no cloud, no LLM, no Docker needed)

## services/billing_api

```text
tests/test_api_auth.py::test_login_success_returns_bearer_token PASSED
tests/test_api_auth.py::test_login_wrong_password PASSED
tests/test_api_auth.py::test_login_unknown_subscriber_same_error PASSED
tests/test_api_auth.py::test_login_validation_error PASSED
tests/test_api_auth.py::test_expired_token_rejected PASSED
tests/test_api_auth.py::test_token_signed_with_other_key_rejected PASSED
tests/test_api_auth.py::test_token_with_wrong_audience_rejected PASSED
tests/test_api_auth.py::test_token_with_unknown_role_rejected PASSED
tests/test_api_auth.py::test_malformed_authorization_header PASSED
tests/test_api_detailed_and_payments.py::test_detailed_breakdown_for_own_bill PASSED
tests/test_api_detailed_and_payments.py::test_detailed_paging PASSED
tests/test_api_detailed_and_payments.py::test_detailed_requires_token PASSED
tests/test_api_detailed_and_payments.py::test_detailed_cannot_read_another_subscriber PASSED
tests/test_api_detailed_and_payments.py::test_detailed_admin_can_read_any_subscriber PASSED
tests/test_api_detailed_and_payments.py::test_detailed_bill_not_found PASSED
tests/test_api_detailed_and_payments.py::test_detailed_invalid_paging PASSED
tests/test_api_detailed_and_payments.py::test_partial_then_full_payment PASSED
tests/test_api_detailed_and_payments.py::test_duplicate_transaction_id_rejected_and_balance_preserved PASSED
tests/test_api_detailed_and_payments.py::test_duplicate_transaction_id_across_subscribers PASSED
tests/test_api_detailed_and_payments.py::test_overpayment_rejected PASSED
tests/test_api_detailed_and_payments.py::test_paying_already_paid_bill_rejected PASSED
tests/test_api_detailed_and_payments.py::test_payment_requires_token PASSED
tests/test_api_detailed_and_payments.py::test_payment_for_missing_bill PASSED
tests/test_api_detailed_and_payments.py::test_payment_validation PASSED
tests/test_api_detailed_and_payments.py::test_payment_always_applies_to_token_owner PASSED
tests/test_api_detailed_and_payments.py::test_health PASSED
tests/test_api_detailed_and_payments.py::test_unknown_route_uses_error_format PASSED
tests/test_api_detailed_and_payments.py::test_openapi_lists_versioned_routes PASSED
tests/test_api_usage_and_calculate.py::test_add_phone_usage_records_10_minutes PASSED
tests/test_api_usage_and_calculate.py::test_add_internet_usage_with_count PASSED
tests/test_api_usage_and_calculate.py::test_add_usage_requires_token PASSED
tests/test_api_usage_and_calculate.py::test_add_usage_forbidden_for_subscriber PASSED
tests/test_api_usage_and_calculate.py::test_add_usage_unknown_subscriber PASSED
tests/test_api_usage_and_calculate.py::test_add_usage_validation PASSED
tests/test_api_usage_and_calculate.py::test_calculate_new_period_without_usage_is_internet_base PASSED
tests/test_api_usage_and_calculate.py::test_calculate_crossing_block_boundary PASSED
tests/test_api_usage_and_calculate.py::test_recalculation_keeps_paid_amount PASSED
tests/test_api_usage_and_calculate.py::test_calculate_forbidden_for_subscriber PASSED
tests/test_api_usage_and_calculate.py::test_calculate_unknown_subscriber PASSED
tests/test_api_usage_and_calculate.py::test_query_bill_success_without_token PASSED
tests/test_api_usage_and_calculate.py::test_query_paid_bill PASSED
tests/test_api_usage_and_calculate.py::test_query_bill_not_calculated PASSED
tests/test_api_usage_and_calculate.py::test_query_bill_validation PASSED
tests/test_api_usage_and_calculate.py::test_query_bill_missing_params PASSED
tests/test_billing_calc.py::test_phone_charge[0-0] PASSED
tests/test_billing_calc.py::test_phone_charge[1000-0] PASSED
tests/test_billing_calc.py::test_phone_charge[1001-10] PASSED
tests/test_billing_calc.py::test_phone_charge[1350-10] PASSED
tests/test_billing_calc.py::test_phone_charge[2000-10] PASSED
tests/test_billing_calc.py::test_phone_charge[2001-20] PASSED
tests/test_billing_calc.py::test_phone_charge[10000-90] PASSED
tests/test_billing_calc.py::test_internet_charge[0-50] PASSED
tests/test_billing_calc.py::test_internet_charge[20000-50] PASSED
tests/test_billing_calc.py::test_internet_charge[20001-60] PASSED
tests/test_billing_calc.py::test_internet_charge[21000-60] PASSED
tests/test_billing_calc.py::test_internet_charge[30000-60] PASSED
tests/test_billing_calc.py::test_internet_charge[30001-70] PASSED
tests/test_billing_calc.py::test_internet_charge[35000-70] PASSED
tests/test_billing_calc.py::test_internet_charge[40000-70] PASSED
tests/test_billing_calc.py::test_worked_example_total_is_80 PASSED
tests/test_billing_calc.py::test_zero_usage_bill_is_internet_base_only PASSED
tests/test_billing_calc.py::test_negative_usage_rejected[phone_charge] PASSED
tests/test_billing_calc.py::test_negative_usage_rejected[internet_charge] PASSED
tests/test_billing_calc.py::test_non_integer_usage_rejected[1.5-phone_charge] PASSED
tests/test_billing_calc.py::test_non_integer_usage_rejected[1.5-internet_charge] PASSED
tests/test_billing_calc.py::test_non_integer_usage_rejected[100-phone_charge] PASSED
tests/test_billing_calc.py::test_non_integer_usage_rejected[100-internet_charge] PASSED
tests/test_billing_calc.py::test_non_integer_usage_rejected[True-phone_charge] PASSED
tests/test_billing_calc.py::test_non_integer_usage_rejected[True-internet_charge] PASSED
tests/test_billing_calc.py::test_due_date_october_2026 PASSED
tests/test_billing_calc.py::test_due_date_crosses_year PASSED
tests/test_billing_calc.py::test_due_date_leap_february PASSED
tests/test_billing_calc.py::test_invalid_period_rejected[2026-0] PASSED
tests/test_billing_calc.py::test_invalid_period_rejected[2026-13] PASSED
tests/test_billing_calc.py::test_invalid_period_rejected[1999-5] PASSED
tests/test_billing_calc.py::test_invalid_period_rejected[2101-1] PASSED
tests/test_billing_calc.py::test_bill_status[80-0-UNPAID] PASSED
tests/test_billing_calc.py::test_bill_status[80-30-PARTIAL] PASSED
tests/test_billing_calc.py::test_bill_status[80-79.99-PARTIAL] PASSED
tests/test_billing_calc.py::test_bill_status[80-80-PAID] PASSED
tests/test_billing_calc.py::test_valid_partial_and_full_payment PASSED
tests/test_billing_calc.py::test_invalid_payment_rejected[0-0-greater than zero] PASSED
tests/test_billing_calc.py::test_invalid_payment_rejected[-5-0-greater than zero] PASSED
tests/test_billing_calc.py::test_invalid_payment_rejected[10.001-0-2 decimal places] PASSED
tests/test_billing_calc.py::test_invalid_payment_rejected[80.01-0-exceeds remaining] PASSED
tests/test_billing_calc.py::test_invalid_payment_rejected[60-30-exceeds remaining] PASSED
tests/test_billing_calc.py::test_invalid_payment_rejected[1-80-already fully paid] PASSED
tests/test_billing_calc.py::test_invalid_payment_rejected[NaN-0-finite] PASSED
tests/test_billing_calc.py::test_invalid_payment_rejected[Infinity-0-finite] PASSED
tests/test_config.py::test_local_defaults_allowed PASSED
tests/test_config.py::test_production_rejects_dev_defaults[overrides0-JWT_SECRET] PASSED
tests/test_config.py::test_production_rejects_dev_defaults[overrides1-JWT_SECRET] PASSED
tests/test_config.py::test_production_rejects_dev_defaults[overrides2-DATABASE_URL] PASSED
tests/test_config.py::test_production_with_real_values PASSED
tests/test_gateway_guard.py::test_no_secret_configured_allows_direct_calls PASSED
tests/test_gateway_guard.py::test_direct_call_without_header_is_rejected PASSED
tests/test_gateway_guard.py::test_wrong_header_is_rejected PASSED
tests/test_gateway_guard.py::test_call_through_gateway_is_allowed PASSED
tests/test_gateway_guard.py::test_health_and_docs_stay_open[/health] PASSED
tests/test_gateway_guard.py::test_health_and_docs_stay_open[/docs] PASSED
tests/test_gateway_guard.py::test_health_and_docs_stay_open[/openapi.json] PASSED
tests/test_models.py::test_full_graph_persists PASSED
tests/test_models.py::test_duplicate_subscriber_no_rejected PASSED
tests/test_models.py::test_one_bill_per_subscriber_period PASSED
tests/test_models.py::test_duplicate_transaction_id_rejected PASSED
tests/test_models.py::test_invalid_usage_rejected[kwargs0] PASSED
tests/test_models.py::test_invalid_usage_rejected[kwargs1] PASSED
tests/test_models.py::test_invalid_usage_rejected[kwargs2] PASSED
tests/test_models.py::test_usage_for_unknown_subscriber_rejected PASSED
======================== 109 passed, 1 warning ========================
```

## services/mcp_server

```text
tests/test_indexer.py::test_document_id_and_name PASSED
tests/test_indexer.py::test_every_numbered_section_is_a_chunk PASSED
tests/test_indexer.py::test_chunk_metadata_and_clean_text PASSED
tests/test_indexer.py::test_preamble_not_indexed PASSED
tests/test_indexer.py::test_parse_minimal_markdown PASSED
tests/test_indexer.py::test_empty_guide_rejected PASSED
tests/test_indexer.py::test_tokenize_stems_and_drops_stopwords PASSED
tests/test_indexer.py::test_required_retrieval_queries[How much does extra internet cost?-8.1-3.2] PASSED
tests/test_indexer.py::test_required_retrieval_queries[Can I pay only part of my bill?-8.3-5.1] PASSED
tests/test_indexer.py::test_required_retrieval_queries[What happens if I pay late?-6.2-6.3] PASSED
tests/test_indexer.py::test_more_policy_queries[How do I dispute a charge?-8.4] PASSED
tests/test_indexer.py::test_more_policy_queries[Why is my bill higher this month?-8.2] PASSED
tests/test_indexer.py::test_more_policy_queries[When is my bill due?-6.1] PASSED
tests/test_indexer.py::test_more_policy_queries[Are there taxes on my bill?-4.2] PASSED
tests/test_indexer.py::test_more_policy_queries[How many free minutes do I get?-2.1] PASSED
tests/test_indexer.py::test_scores_are_descending PASSED
tests/test_indexer.py::test_unrelated_query_returns_nothing PASSED
tests/test_indexer.py::test_stopword_only_query_returns_nothing PASSED
tests/test_server.py::test_tool_is_listed_with_schema PASSED
tests/test_server.py::test_search_returns_guide_format PASSED
tests/test_server.py::test_default_top_k_is_three PASSED
tests/test_server.py::test_no_matches_is_not_an_error PASSED
tests/test_server.py::test_blank_query_is_tool_error PASSED
tests/test_server.py::test_invalid_arguments_rejected[args0] PASSED
tests/test_server.py::test_invalid_arguments_rejected[args1] PASSED
tests/test_server.py::test_invalid_arguments_rejected[args2] PASSED
tests/test_server.py::test_invalid_arguments_rejected[args3] PASSED
============================== 27 passed ==============================
```

## services/agent

```text
tests/test_gemini.py::test_tools_use_raw_json_schema PASSED
tests/test_gemini.py::test_tool_results_are_grouped_and_raw_model_turn_replayed PASSED
tests/test_gemini.py::test_api_only_question PASSED
tests/test_gemini.py::test_combined_question_runs_parallel_calls PASSED
tests/test_gemini.py::test_gemini_cannot_pay_without_user_confirmation PASSED
tests/test_gemini.py::test_two_payments_in_one_turn_are_not_both_prepared PASSED
tests/test_gemini.py::test_gemini_api_error_is_reported_and_history_stays_valid PASSED
tests/test_gemini.py::test_blocked_response_gets_a_safe_answer PASSED
tests/test_gemini.py::test_injected_subscriber_number_is_ignored PASSED
tests/test_gemini.py::test_gemini_requires_api_key PASSED
tests/test_gemini.py::test_gemini_provider_built_from_settings PASSED
tests/test_gemini.py::test_unknown_provider PASSED
tests/test_gemini.py::test_free_tier_rate_limit_message PASSED
tests/test_gemini.py::test_last_round_offers_no_tools_so_the_model_must_answer PASSED
tests/test_safety.py::test_no_cancels_payment PASSED
tests/test_safety.py::test_other_message_is_not_consent PASSED
tests/test_safety.py::test_vague_answers_do_not_pay[ok] PASSED
tests/test_safety.py::test_vague_answers_do_not_pay[sure] PASSED
tests/test_safety.py::test_vague_answers_do_not_pay[maybe] PASSED
tests/test_safety.py::test_vague_answers_do_not_pay[yes but how much is it?] PASSED
tests/test_safety.py::test_yes_without_pending_payment_pays_nothing PASSED
tests/test_safety.py::test_partial_payment_amount PASSED
tests/test_safety.py::test_amount_above_balance_is_refused_before_confirmation PASSED
tests/test_safety.py::test_already_paid_bill PASSED
tests/test_safety.py::test_lost_response_is_retried_with_same_transaction_id PASSED
tests/test_safety.py::test_payment_rejected_by_api_is_not_reported_as_success PASSED
tests/test_safety.py::test_other_subscriber_number_in_prompt_is_refused PASSED
tests/test_safety.py::test_no_tool_accepts_a_subscriber_number PASSED
tests/test_safety.py::test_executor_ignores_subscriber_number_from_llm PASSED
tests/test_safety.py::test_missing_bill_is_not_estimated PASSED
tests/test_safety.py::test_docs_service_down PASSED
tests/test_safety.py::test_no_docs_match PASSED
tests/test_safety.py::test_unknown_tool_from_llm PASSED
tests/test_safety.py::test_tool_loop_is_bounded PASSED
tests/test_safety.py::test_non_finite_amount_from_llm_is_rejected PASSED
tests/test_scenarios.py::test_mcp_only_extra_internet_cost PASSED
tests/test_scenarios.py::test_api_only_october_bill PASSED
tests/test_scenarios.py::test_combined_why_is_october_higher PASSED
tests/test_scenarios.py::test_pay_bill_requires_explicit_confirmation PASSED
tests/test_scenarios.py::test_turkish_conversation_routes_the_same PASSED
tests/test_scenarios.py::test_assignment_example_internet_charge_this_month PASSED
tests/test_units.py::test_parse_period[What is my October bill?-expected0] PASSED
tests/test_units.py::test_parse_period[my oct bill-expected1] PASSED
tests/test_units.py::test_parse_period[bill for December-expected2] PASSED
tests/test_units.py::test_parse_period[April 2025 bill-expected3] PASSED
tests/test_units.py::test_parse_period[my bill in may-expected4] PASSED
tests/test_units.py::test_parse_period[May I pay part of my bill?-None] PASSED
tests/test_units.py::test_parse_period[this month-expected6] PASSED
tests/test_units.py::test_parse_period[Why is my internet charge higher this month?-expected7] PASSED
tests/test_units.py::test_parse_period[last month's bill-expected8] PASSED
tests/test_units.py::test_parse_period[Ekim faturam ne kadar?-expected9] PASSED
tests/test_units.py::test_parse_period[ekimdeki fatura-expected10] PASSED
tests/test_units.py::test_parse_period[Eyl\xfcl 2026 faturas\u0131-expected11] PASSED
tests/test_units.py::test_parse_period[ge\xe7en ay-expected12] PASSED
tests/test_units.py::test_parse_period[Pay my bill-None] PASSED
tests/test_units.py::test_default_period_is_last_finished_month PASSED
tests/test_units.py::test_system_prompt_pins_identity_and_date PASSED
tests/test_units.py::test_client_sends_bearer_and_gateway_key PASSED
tests/test_units.py::test_client_raises_api_error_with_code PASSED
tests/test_units.py::test_protected_call_without_login_fails_locally PASSED
tests/test_units.py::test_network_error_is_api_unavailable PASSED
tests/test_units.py::test_non_json_error_body PASSED
============================== 62 passed ==============================
```

