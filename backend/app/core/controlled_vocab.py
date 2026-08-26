# Destination path: backend/app/core/controlled_vocab.py
# Replaces the existing file in full.
#
# CHANGE (Known Gap item 19 fix, this session): USE_CASES was a
# separate, hand-maintained list that had already drifted out of sync
# with app/core/use_case_classifier.py's real output space -- it was
# missing "Customer Service Chatbots" entirely, meaning GET /vocab's
# use_cases key has been silently wrong since Phase 5 shipped. Fixed
# by re-exporting use_case_classifier.py's USE_CASE_CATEGORIES (which
# is itself derived from USE_CASE_MAPPING.keys(), the actual keyword
# mapping classify_use_cases() runs against) under the same USE_CASES
# name, so GET /vocab now always reflects the classifier's true output
# space with zero manual sync required. No other list in this file
# changed.

from app.core.use_case_classifier import USE_CASE_CATEGORIES as USE_CASES

KNOWN_TASK_TYPES = [
    "Safety", "Jailbreak", "Red Teaming", "Bias", "Hallucination", "Toxicity",
    "Alignment", "Value Alignment", "Moral", "Trustworthiness",
    "Helpfulness Eval", "Preference Eval", "Satisfaction Eval",
    "Privacy", "Prompt Extraction", "Cyberattacks", "Unlearning",
    "Agents Safety", "Agents Behavior Detection", "Reasoning",
    "Refusal", "False Refusal", "Over Refusal", "Non-compliance",
    "Consistency", "Calibration",
    "Instruction-following", "Rule-following", "RAG", "Multimodal",
    "Conversational Safety", "Opinion Steering", "Causal Reasoning",
    "Benchmark", "Evaluation", "Crowdsourced", "Lie Detection",
    "Capabilities", "Language",
]

ENTRY_MODALITIES = [
    "Prompts", "Conversations", "Examples", "Binary-choice Questions",
    "Multiple-choice Questions", "Scenarios", "Sentences", "Excerpts",
    "Posts", "Sentence Pairs", "Entry Tuples", "Location Templates",
    "Stories", "Comments", "Anecdotes", "Transcripts", "Entry Tuples",
]

CREATED_BY = ["Human", "Machine", "Hybrid"]
DEV_PURPOSE = ["Eval", "Train", "Train & Eval"]
INTEGRATION_OPTION = ["API", "Export", "API & Export", "NA"]
COMPLEXITY_LEVEL = ["Popular", "High", "Medium", "Low", "Unknown"]
CODE_DATASET = ["Yes", "No"]
LANGUAGE_SUPPORT = ["en", "zh", "ar", "fr", "hi", "ko", "Multilingual"]
