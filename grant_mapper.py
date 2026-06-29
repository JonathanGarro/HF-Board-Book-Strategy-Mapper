import pandas as pd
import re

input_file = '00OUf00000L9vvwMAB.csv'
mapping_file = 'strategy_mapping.csv'
output_file = 'outputs/00OUf00000L9vvwMAB_mapped.csv'

# load the grants data with proper encoding
# use latin1 which is compatible with cp1252 and handles special characters better
df = pd.read_csv(input_file, encoding='latin1')

# load mapping rules
mapping_df = pd.read_csv(mapping_file, encoding='utf-8')

text_columns = ['Board Book Top Level Program', 'Board Book Section Title', 'Primary Strategy',
                'Organization: Organization Name', 'Project Title']

key_columns = ['Board Book Top Level Program', 'Board Book Section Title', 'Primary Strategy']


def clean_text(series):
    """clean lossy/mojibake characters from a text column without damaging real words"""
    s = series.astype(str)
    # one-off fixes where the source export destroyed non-latin letters into '?'
    # and the original characters cannot be recovered automatically
    known_corrections = {
        'N? Lei Hulu i ka W?kiu': 'N\u0101 Lei Hulu i ka W\u0113kiu',
    }
    for bad, good in known_corrections.items():
        s = s.str.replace(bad, good, regex=False)
    # the gms export substitutes a literal '?' for characters it cannot encode.
    # only treat '?' as a lost apostrophe in the common possessive/contraction shapes:
    # women?s (before s), lawyers? committee (after a word ending in s), and any '?'
    # sitting inside a word. an isolated '? ' surrounded by spaces is almost always a
    # lost dash. everything else is left untouched rather than blanket-replacing all '?'.
    s = s.str.replace(r"(?<=\w)\?(?=\w)", "'", regex=True)
    s = s.str.replace(r"(?<=\w)\?(?=s\b)", "'", regex=True)
    s = s.str.replace(r"(?<=[sS])\?(?=\s|$|[,.;:)\]])", "'", regex=True)
    s = s.str.replace(r"\s\?\s", " - ", regex=True)
    # real curly apostrophes, if any survive, normalized to a straight apostrophe
    s = s.str.replace('\u2019', "'", regex=False)
    s = s.str.replace('\u2018', "'", regex=False)
    # specific mojibake sequences, each mapped to a single distinct target
    s = s.str.replace('\u00e2\u20ac\u2122', "'", regex=False)   # curly apostrophe
    s = s.str.replace('\u00e2\u20ac\u201c', "-", regex=False)   # en dash
    s = s.str.replace('\u00e2\u20ac\u201d', "-", regex=False)   # em dash
    s = s.str.replace('\u00e2\u20ac\u0153', '"', regex=False)   # left double quote
    s = s.str.replace('\u00e2\u20ac\u009d', '"', regex=False)   # right double quote
    return s


# clean every text column in the grants data
for col in text_columns:
    if col in df.columns:
        df[col] = clean_text(df[col])

# clean the same key columns in the mapping so apostrophes/dashes match on both sides
for col in key_columns:
    if col in mapping_df.columns:
        mapping_df[col] = clean_text(mapping_df[col])

# apply post-load corrections to strategy_mapping.csv:
# geg: women's funds collaborative initiative grants map to OTHER (not their own strategy name)
# sp: grants with primary strategy "special projects" map to OTHER (not SPECIAL PROJECTS)
mapping_df.loc[
    (mapping_df['Board Book Top Level Program'].str.upper().str.strip() == 'GENDER EQUITY & GOVERNANCE') &
    (mapping_df['Board Book Section Title'].str.upper().str.strip() == "WOMEN'S FUNDS COLLABORATIVE INITIATIVE"),
    'Strategy'
] = 'OTHER'

mapping_df.loc[
    (mapping_df['Board Book Top Level Program'].str.upper().str.strip() == 'SPECIAL PROJECTS') &
    (mapping_df['Primary Strategy'].str.upper().str.strip() == 'SPECIAL PROJECTS') &
    (mapping_df['Board Book Section Title'].fillna('').str.strip() == ''),
    'Strategy'
] = 'OTHER'

mapping_df = mapping_df.fillna('')
df = df.fillna('')


def normalize(series):
    """uppercase + strip, then blank out only cells whose entire value is 'nan'.
    using a whole-cell replace (not a substring replace) avoids mangling real
    words that happen to contain the letters n-a-n, e.g. governance, finance."""
    return series.astype(str).str.upper().str.strip().replace('NAN', '')


for col in key_columns:
    if col in mapping_df.columns:
        mapping_df[f'{col}_NORMALIZED'] = normalize(mapping_df[col])
    if col in df.columns:
        df[f'{col}_NORMALIZED'] = normalize(df[col])

# initialize new columns
df['Program'] = ''
df['Strategy'] = ''
df['Substrategy'] = ''


# create a lookup key for matching
# 1. match on all three fields (board book top level, section title, primary strategy)
# 2. match on board book top level and primary strategy (section title blank in mapping)
# 3. match on board book top level and section title (primary strategy blank in mapping)
# 4. match on board book top level only

def apply_mapping(row):
    """apply mapping rules to a single row by matching against the mapping table.
    returns tuple of (program, strategy, substrategy)"""
    bb_program = row['Board Book Top Level Program_NORMALIZED']
    bb_section = row['Board Book Section Title_NORMALIZED']
    primary_strat = row['Primary Strategy_NORMALIZED']

    # try exact match on all three fields
    match = mapping_df[
        (mapping_df['Board Book Top Level Program_NORMALIZED'] == bb_program) &
        (mapping_df['Board Book Section Title_NORMALIZED'] == bb_section) &
        (mapping_df['Primary Strategy_NORMALIZED'] == primary_strat)
        ]

    if len(match) > 0:
        return (
            match.iloc[0]['Program'],
            match.iloc[0]['Strategy'],
            match.iloc[0].get('SUBSTRATEGY', '')
        )

    # try match on board book top level and primary strategy when section title is empty in mapping
    # this handles cases like climate where section title varies but primary strategy is key
    match = mapping_df[
        (mapping_df['Board Book Top Level Program_NORMALIZED'] == bb_program) &
        (mapping_df['Board Book Section Title_NORMALIZED'] == '') &
        (mapping_df['Primary Strategy_NORMALIZED'] == primary_strat)
        ]

    if len(match) > 0:
        return (
            match.iloc[0]['Program'],
            match.iloc[0]['Strategy'],
            match.iloc[0].get('SUBSTRATEGY', '')
        )

    # try match on board book top level and section title
    match = mapping_df[
        (mapping_df['Board Book Top Level Program_NORMALIZED'] == bb_program) &
        (mapping_df['Board Book Section Title_NORMALIZED'] == bb_section) &
        (mapping_df['Primary Strategy_NORMALIZED'] == '')
        ]

    if len(match) > 0:
        return (
            match.iloc[0]['Program'],
            match.iloc[0]['Strategy'],
            match.iloc[0].get('SUBSTRATEGY', '')
        )

    # try match on board book top level only
    match = mapping_df[
        (mapping_df['Board Book Top Level Program_NORMALIZED'] == bb_program) &
        (mapping_df['Board Book Section Title_NORMALIZED'] == '') &
        (mapping_df['Primary Strategy_NORMALIZED'] == '')
        ]

    if len(match) > 0:
        return (
            match.iloc[0]['Program'],
            match.iloc[0]['Strategy'],
            match.iloc[0].get('SUBSTRATEGY', '')
        )

    # no match found - return empty values
    return ('', '', '')


# apply mapping to all rows
print("\napplying mapping rules...")
df[['Program', 'Strategy', 'Substrategy']] = df.apply(
    lambda row: pd.Series(apply_mapping(row)),
    axis=1
)

# uppercase the substrategy column to match program and strategy
df['Substrategy'] = df['Substrategy'].str.upper()

# count unmapped records
unmapped = df[(df['Program'] == '') & (df['Board Book Top Level Program'] != '')]
if len(unmapped) > 0:
    print(f"\nwarning: {len(unmapped)} records could not be mapped")
    print("\nsample unmapped records:")
    print(unmapped[['Board Book Top Level Program', 'Board Book Section Title',
                    'Primary Strategy']].drop_duplicates().head(10))
else:
    print("\nall records mapped successfully")

# show distribution of results
print(f"\nmapping complete. mapped {len(df[df['Program'] != ''])} of {len(df)} records")
print("\nprogram distribution:")
print(df['Program'].value_counts().to_string())
print("\nstrategy distribution:")
print(df['Strategy'].value_counts().to_string())

# drop the original matching columns and keep only the normalized ones
# rename the normalized columns to remove the _NORMALIZED suffix
df = df.drop(columns=['Board Book Top Level Program', 'Board Book Section Title', 'Primary Strategy'])
df = df.rename(columns={
    'Board Book Top Level Program_NORMALIZED': 'Board Book Top Level Program',
    'Board Book Section Title_NORMALIZED': 'Board Book Section Title',
    'Primary Strategy_NORMALIZED': 'Primary Strategy'
})

import os
os.makedirs('outputs', exist_ok=True)
df.to_csv(output_file, index=False, encoding='utf-8-sig')
print(f"\noutput saved to: {output_file}")
print("\nnote: output file uses utf-8 encoding with properly normalized text")