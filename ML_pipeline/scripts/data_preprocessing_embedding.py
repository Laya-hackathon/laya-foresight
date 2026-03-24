import pandas as pd


# =========================
# 1. LOAD DATA
# =========================
def load_data(filepath: str) -> pd.DataFrame:
    df = pd.read_csv(filepath)
    return df


# =========================
# 2. CLEANING
# =========================
def drop_unnecessary_columns(df: pd.DataFrame) -> pd.DataFrame:
    cols_to_drop = ['days_since_resubmission']
    df = df.drop(columns=cols_to_drop, errors='ignore')
    return df


def remove_duplicates(df: pd.DataFrame) -> pd.DataFrame:
    df = df.drop_duplicates()
    return df


# =========================
# 3. STANDARDIZATION
# =========================
def standardize_region(df: pd.DataFrame) -> pd.DataFrame:
    if 'region' not in df.columns:
        return df

    df['region'] = df['region'].str.lower()

    region_mapping = {
        'county dublin': 'dublin',
        'co. dublin': 'dublin',
        'cork': 'cork',
        'county cork': 'cork',
        'co. cork': 'cork',
        'galway': 'galway',
        'county galway': 'galway',
        'limerick': 'limerick',
        'co. limerick': 'limerick',
        'lk': 'limerick',
        'waterford': 'waterford',
        'rest of ireland': 'other'
    }

    df['region'] = df['region'].replace(region_mapping)
    return df


def standardize_submission_channel(df: pd.DataFrame) -> pd.DataFrame:
    if 'submission_channel' not in df.columns:
        return df

    df['submission_channel'] = df['submission_channel'].str.lower()

    mapping = {
        'mobile app': 'app',
        'laya app': 'app',
        'post': 'paper_post',
        'paper': 'paper_post',
        'web': 'web_portal',
        'web portal': 'web_portal',
        'directbilling': 'direct_billing'
    }

    df['submission_channel'] = df['submission_channel'].replace(mapping)
    return df


# =========================
# 4. FEATURE SELECTION
# =========================
def drop_low_value_features(df: pd.DataFrame) -> pd.DataFrame:
    features_to_drop = ['region', 'plan_type']
    df = df.drop(columns=features_to_drop, errors='ignore')
    return df


# =========================
# 5. ENCODING
# =========================
def encode_features(df: pd.DataFrame) -> pd.DataFrame:
    categorical_cols = ['submission_channel', 'treatment_type', 'age_group']

    df_encoded = pd.get_dummies(
        df,
        columns=[col for col in categorical_cols if col in df.columns],
        drop_first=True
    )

    return df_encoded


def convert_bool_to_int(df: pd.DataFrame) -> pd.DataFrame:
    bool_cols = df.select_dtypes(include='bool').columns
    for col in bool_cols:
        df[col] = df[col].astype(int)
    return df


def drop_target_leakage(df: pd.DataFrame) -> pd.DataFrame:
    cols_to_drop = ['label_escalation_48h', 'sla_breach_flag']
    df = df.drop(columns=cols_to_drop, errors='ignore')
    return df


# =========================
# 6. SAVE
# =========================
def save_data(df: pd.DataFrame, output_path: str):
    df.to_csv(output_path, index=False)


# =========================
# 7. FULL PIPELINE
# =========================
def preprocess_and_encode(input_path: str, output_path: str) -> pd.DataFrame:
    df = load_data(input_path)

    df = drop_unnecessary_columns(df)
    df = remove_duplicates(df)

    df = standardize_region(df)
    df = standardize_submission_channel(df)

    df = drop_low_value_features(df)

    df = encode_features(df)
    df = convert_bool_to_int(df)

    df = drop_target_leakage(df)

    save_data(df, output_path)

    return df