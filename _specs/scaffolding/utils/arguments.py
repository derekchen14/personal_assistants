import argparse


def solicit_params():
    parser = argparse.ArgumentParser()

    # Required parameters
    parser.add_argument(
        "--input-dir",
        default="annotations",
        type=str,
        help="The input training data file which is a JSON file.",
    )
    parser.add_argument(
        "--output-dir",
        default="results",
        type=str,
        help="Output directory where the model predictions and checkpoints are written.",
    )
    parser.add_argument(
        "--task",
        default="joint",
        type=str,
        choices=["joint", "tab_col", "agg_op", "thought", "sql", "response"],
        help="which task we are training the model on",
    )
    parser.add_argument(
        "--model",
        default="bert",
        choices=["bert", "gpt", "t5", "godel"],
        help="The model architecture to be learned or fine-tuned.",
    )
    parser.add_argument(
        "--size",
        default="small",
        choices=["small", "medium", "large", "giant"],
        help="Models size to be trained or evaluated on.",
    )
    parser.add_argument(
        "--method",
        default="standard",
        help="Method of training the model, can hold different settings",
    )
    parser.add_argument(
        "--checkpoint",
        default="",
        type=str,
        help="Enter the filename of a checkpoint for manual override",
    )
    parser.add_argument("--seed", default=42, type=int)

    # Key settings
    parser.add_argument(
        "--ignore-cache",
        action="store_true",
        help="Whether to ignore cache and create a new input data",
    )
    parser.add_argument(
        "--api-version",
        default="gpt-4o",
        help="Which version of third party API to run",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Whether to allow crashing errors for stack trace.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Whether to run with extra prints to help debug",
    )
    parser.add_argument(
        "--do-nlu", action="store_true", help="Whether to run the test suite for nlu."
    )
    parser.add_argument(
        "--run-beta",
        action="store_true",
        help="Whether to run the beta version of the test suite for nlu.",
    )
    parser.add_argument(
        "--test-expert",
        default="embed",
        choices=["regex", "embed", "logreg", "peft", "icl", "all"],
        help="The model architecture to be learned or fine-tuned.",
    )
    parser.add_argument(
        "--allow-dev-mode",
        action="store_true",
        help="Whether to allow running in development mode with gold dax and direct DB access",
    )

    # Training parameters
    parser.add_argument(
        "--qualify",
        action="store_true",
        help="Whether to include joint accuracy scores during evaluation",
    )
    parser.add_argument(
        "--quantify",
        action="store_true",
        help="Whether to include inform/success/BLEU scores during evaluation",
    )
    parser.add_argument(
        "--batch-size",
        default=12,
        type=int,
        help="Batch size per GPU/CPU for training and evaluation.",
    )
    parser.add_argument(
        "--drop-rate", default=0.1, type=float, help="Dropout rate with default of 10%"
    )
    parser.add_argument(
        "--threshold",
        default=0.6,
        type=float,
        help="Used as limit for intent classification or fallback to PEFT and ICL",
    )
    parser.add_argument(
        "--temperature",
        default=0.1,
        type=float,
        help="Temperature for increasing diversity when decoding, mainly for paraphrase",
    )
    parser.add_argument(
        "--level",
        default="cosine",
        type=str,
        help="Indicates amount of noise to inject into MWOZ or the subset of data, \
        valid options: clean, noisy, delex, frame, original,  15percent, 30percent",
    )
    parser.add_argument(
        "--max-length",
        default=512,
        type=int,
        help="Length of the generated output for DST, effectively means the min length",
    )

    args = parser.parse_args()
    return args
