import os

import sys

import numpy as np

import pandas as pd


def test_student_submission():


    print("  HACKSPHERE 3.0 - Pre-Submission Self-Tester    ")



    if not os.path.exists("predict.py"):

        print(" ERROR: 'predict.py' not found in current folder!")

        sys.exit(1)

    print(" Found 'predict.py'.")


    if not os.path.exists("sample_test_input.csv"):

        print(" ERROR: 'sample_test_input.csv' not found!")

        sys.exit(1)

    print(" Found 'sample_test_input.csv'.")


    try:

        from predict import predict

    except ImportError as e:

        print(f" ERROR: Failed to import 'predict' from predict.py: {e}")

        sys.exit(1)

    print(" Successfully imported 'predict(input_df)' function.")


    test_df = pd.read_csv("sample_test_input.csv")

    print(f"Loaded {len(test_df)} test rows from 'sample_test_input.csv'.")


    try:

        predictions = predict(test_df)

    except Exception as e:

        print(

            f" ERROR: Execution of predict(test_df) crashed with error:\n{e}"

        )

        sys.exit(1)


    if not isinstance(predictions, (np.ndarray, list)):

        print(

            f" ERROR: predict() must return a numpy array or list, got {type(predictions)}."

        )

        sys.exit(1)


    predictions = np.array(predictions)


    if len(predictions) != len(test_df):

        print(

            f" ERROR: Size mismatch! Expected {len(test_df)} predictions, got {len(predictions)}."

        )

        sys.exit(1)


    if np.isnan(predictions).any() or np.isinf(predictions).any():

        print(" ERROR: Predictions contain NaN or Infinite values!")

        sys.exit(1)



    print("Your predict.py script is completely valid!")

    print(f"   Sample output values: {np.round(predictions[:3], 2)}...")
    
    print("SUCCESS")

   


if __name__ == "__main__":

    test_student_submission() 