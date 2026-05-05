# One policy file per intent. Three universal intents (converse, plan,
# internal) plus four domain-specific intents whose names the domain chooses
# (Hugo: research, draft, revise, publish; Dana: clean, transform, analyze,
# report). Flows within a file are dispatched by `match flow.name():`.
#
# from backend.modules.policies.converse import ConversePolicies
# from backend.modules.policies.plan import PlanPolicies
# from backend.modules.policies.internal import InternalPolicies
# # plus the four domain-specific intent files:
# # from backend.modules.policies.<intent_a> import <IntentA>Policies
# # from backend.modules.policies.<intent_b> import <IntentB>Policies
# # from backend.modules.policies.<intent_c> import <IntentC>Policies
# # from backend.modules.policies.<intent_d> import <IntentD>Policies
#
# __all__ = [
#     'ConversePolicies', 'PlanPolicies', 'InternalPolicies',
#     # plus domain intent class names
# ]
