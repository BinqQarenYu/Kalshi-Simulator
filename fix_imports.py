import os
import re

directories = ['app_1_machine_engine', 'app_2_execution_bot', 'app_3_autonomous_chef', 'shared', 'tests', 'scripts']

# We need to map from 'kalshi_sim.module' to the new absolute paths.
mappings = {
    'kalshi_sim.ml.train_model': 'app_1_machine_engine.ml.train_model',
    'kalshi_sim.ml.continuous_trainer': 'app_1_machine_engine.ml.continuous_trainer',
    'kalshi_sim.ml.dataset_builder': 'app_1_machine_engine.ml.dataset_builder',
    'kalshi_sim.ml.export_onnx': 'app_1_machine_engine.ml.export_onnx',
    'kalshi_sim.ml.gold_continuous_trainer': 'app_1_machine_engine.ml.gold_continuous_trainer',
    'kalshi_sim.ml.gold_dataset_builder': 'app_1_machine_engine.ml.gold_dataset_builder',
    'kalshi_sim.ml.gold_model': 'app_1_machine_engine.ml.gold_model',
    'kalshi_sim.ml.model': 'app_1_machine_engine.ml.model',
    'kalshi_sim.data_hygiene': 'app_1_machine_engine.data_hygiene',
    'kalshi_sim.ohlcv_aggregator': 'app_1_machine_engine.ohlcv_aggregator',
    'kalshi_sim.tick_writer': 'app_1_machine_engine.tick_writer',
    'kalshi_sim.server': 'app_2_execution_bot.server',
    'kalshi_sim.live_coordinator': 'app_2_execution_bot.live_coordinator',
    'kalshi_sim.order_client': 'app_2_execution_bot.order_client',
    'kalshi_sim.ws_connection': 'app_2_execution_bot.ws_connection',
    'kalshi_sim.orderbook': 'app_2_execution_bot.orderbook',
    'kalshi_sim.rate_limiter': 'app_2_execution_bot.rate_limiter',
    'kalshi_sim.exchange_router': 'app_2_execution_bot.exchange_router',
    'kalshi_sim.ml.feature_extractor': 'app_2_execution_bot.ml.feature_extractor',
    'kalshi_sim.ml.onnx_engine': 'app_2_execution_bot.ml.onnx_engine',
    'kalshi_sim.ml.gold_feature_extractor': 'app_2_execution_bot.ml.gold_feature_extractor',
    'kalshi_sim.domination_bot': 'app_2_execution_bot.domination_bot',
    'kalshi_sim.macro_trend_dominion_bot': 'app_2_execution_bot.macro_trend_dominion_bot',
    'kalshi_sim.dual_onnx_bot': 'app_2_execution_bot.dual_onnx_bot',
    'kalshi_sim.dual_onnx_gateway': 'app_2_execution_bot.dual_onnx_gateway',
    'kalshi_sim.dual_onnx_strategy': 'app_2_execution_bot.dual_onnx_strategy',
    'kalshi_sim.standalone_bot': 'app_2_execution_bot.standalone_bot',
    'kalshi_sim.system_governor': 'app_3_autonomous_chef.system_governor',
    'kalshi_sim.incubator_manager': 'app_3_autonomous_chef.incubator_manager',
    'kalshi_sim.incubator_agent': 'app_3_autonomous_chef.incubator_agent',
    'kalshi_sim.bot_deployment_auditor': 'app_3_autonomous_chef.bot_deployment_auditor',
    'kalshi_sim.strategy_evaluator': 'app_3_autonomous_chef.strategy_evaluator',
    'kalshi_sim.remote_control': 'app_3_autonomous_chef.remote_control',
    'kalshi_sim.poe_flight_recorder': 'app_3_autonomous_chef.poe_flight_recorder',
    'kalshi_sim.schemas': 'shared.schemas',
    'kalshi_sim.dual_onnx_schemas': 'shared.dual_onnx_schemas',
    'kalshi_sim.auth': 'shared.auth',
    'kalshi_sim.cfbenchmarks_sync': 'shared.cfbenchmarks_sync',
    'kalshi_sim.clock_sync': 'shared.clock_sync',
    'kalshi_sim.base_engine': 'shared.base_engine',
}

def process_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    modified = content

    for old, new in mappings.items():
        modified = modified.replace(f"from {old}", f"from {new}")
        modified = modified.replace(f"import {old}", f"import {new}")
        
    for old, new in mappings.items():
        old_parent = '.'.join(old.split('.')[:-1])
        old_child = old.split('.')[-1]
        new_parent = '.'.join(new.split('.')[:-1])
        new_child = new.split('.')[-1]
        
        if old_parent and new_parent:
            modified = modified.replace(f"from {old_parent} import {old_child}", f"from {new_parent} import {new_child}")

    # Final sweep
    modified = modified.replace("kalshi_sim.ml.", "app_1_machine_engine.ml.")
    # But wait! 'kalshi_sim' could be used everywhere.
    modified = modified.replace("from kalshi_sim import ", "from shared import ")
    modified = modified.replace("import kalshi_sim", "import shared")

    if modified != content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(modified)
        print(f"Updated {filepath}")

for d in directories:
    if os.path.exists(d):
        for root, _, files in os.walk(d):
            for file in files:
                if file.endswith('.py'):
                    process_file(os.path.join(root, file))

print("Imports fixed properly.")
