# Generation Tasks for 5 Baselines

# Zero-Shot

python ../generation_task/benchmark_generation.py --model=claude3hk --task=zero-shot --topic=travel_restaurant --inter_turn=2
python ../generation_task/llm_based_evaluation_errortypes.py --model=claude3hk --task=zero-shot --topic=travel_restaurant --inter_turn=2 --pref_form=explicit
python ../generation_task/get_preference_following_accuracy_generation_task.py --model=claude3hk --task=zero-shot --topic=travel_restaurant --inter_turn=2 --pref_form=explicit

# Reminder
python ../generation_task/benchmark_generation.py --model=claude3hk --task=remind --topic=travel_restaurant --inter_turn=2
python ../generation_task/llm_based_evaluation_errortypes.py --model=claude3hk --task=remind --topic=travel_restaurant --inter_turn=2 --pref_form=explicit
python ../generation_task/get_preference_following_accuracy_generation_task.py --model=claude3hk --task=remind --topic=travel_restaurant --inter_turn=2 --pref_form=explicit

# CoT
python ../generation_task/benchmark_generation.py --model=claude3hk --task=cot --topic=travel_restaurant --inter_turn=2
python ../generation_task/llm_based_evaluation_errortypes.py --model=claude3hk --task=cot --topic=travel_restaurant --inter_turn=2 --pref_form=explicit
python ../generation_task/get_preference_following_accuracy_generation_task.py --model=claude3hk --task=cot --topic=travel_restaurant --inter_turn=2 --pref_form=explicit

# Self-Critic
python ../generation_task/benchmark_generation.py --model=claude3hk --task=selfcritic --topic=travel_restaurant --inter_turn=2
python ../generation_task/llm_based_evaluation_errortypes.py --model=claude3hk --task=selfcritic --topic=travel_restaurant --inter_turn=2 --pref_form=explicit
python ../generation_task/get_preference_following_accuracy_generation_task.py --model=claude3hk --task=selfcritic --topic=travel_restaurant --inter_turn=2 --pref_form=explicit

# RAG
python ../generation_task/benchmark_generation.py --model=claude3hk --task=rag --topic=travel_restaurant --inter_turn=2
python ../generation_task/llm_based_evaluation_errortypes.py --model=claude3hk --task=rag_5 --topic=travel_restaurant --inter_turn=2 --pref_form=explicit
python ../generation_task/get_preference_following_accuracy_generation_task.py --model=claude3hk --task=rag_5 --topic=travel_restaurant --inter_turn=2 --pref_form=explicit
