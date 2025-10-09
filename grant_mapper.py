import pandas as pd

input_file = '00OUf000008PyafMAC.csv'
mapping_file = 'strategy_mapping.csv'
output_file = '00OUf000008PyafMAC_mapped.csv'

# load the grants data with proper encoding
# use latin1 which is compatible with cp1252 and handles special characters better
df = pd.read_csv(input_file, encoding='latin1')

# load mapping rules
mapping_df = pd.read_csv(mapping_file, encoding='utf-8')

text_columns = ['Board Book Top Level Program', 'Board Book Section Title', 'Primary Strategy',
                'Organization: Organization Name', 'Project Title']

# for whatever reason the GMS export is super messy, so im manually fixing character issues
for col in text_columns:
    if col in df.columns:
        # fix various types of apostrophes - replace ALL with straight apostrophe (char 39)
        df[col] = df[col].astype(str).str.replace('?', "'", regex=False)  # question mark from encoding issue
        df[col] = df[col].str.replace('â€™', "'", regex=False)  # corrupted curly apostrophe
        df[col] = df[col].str.replace('Ã¢â‚¬â„¢', "'", regex=False)  # another corrupted version
        df[col] = df[col].str.replace('\u2019', "'", regex=False)  # right single quotation mark
        df[col] = df[col].str.replace('\u2018', "'", regex=False)  # left single quotation mark
        # corrupted dashes
        df[col] = df[col].str.replace('â€"', "–", regex=False)
        df[col] = df[col].str.replace('â€"', "—", regex=False)
        # corrupted quotes
        df[col] = df[col].str.replace('â€œ', '"', regex=False)
        df[col] = df[col].str.replace('â€', '"', regex=False)

# also fix the same issues in mapping file
for col in ['Board Book Top Level Program', 'Board Book Section Title', 'Primary Strategy']:
    if col in mapping_df.columns:
        mapping_df[col] = mapping_df[col].astype(str).str.replace('?', "'", regex=False)
        mapping_df[col] = mapping_df[col].str.replace('â€™', "'", regex=False)
        mapping_df[col] = mapping_df[col].str.replace('Ã¢â‚¬â„¢', "'", regex=False)
        mapping_df[col] = mapping_df[col].str.replace('\u2019', "'",
                                                      regex=False)  # right single quotation mark
        mapping_df[col] = mapping_df[col].str.replace('\u2018', "'",
                                                      regex=False)  # left single quotation mark

# clean up column names and handle missing values
mapping_df = mapping_df.fillna('')
df = df.fillna('')

for col in ['Board Book Top Level Program', 'Board Book Section Title', 'Primary Strategy']:
    if col in mapping_df.columns:
        # convert to string, replace 'nan' with empty string, then uppercase and strip
        mapping_df[f'{col}_NORMALIZED'] = mapping_df[col].astype(str).str.replace('nan', '',
                                                                                  regex=False).str.upper().str.strip()
    if col in df.columns:
        # convert to string, replace 'nan' with empty string, then uppercase and strip
        df[f'{col}_NORMALIZED'] = df[col].astype(str).str.replace('nan', '', regex=False).str.upper().str.strip()

# initialize new columns
df['Program'] = ''
df['Strategy'] = ''
df['Substrategy'] = ''


# create a lookup key for matching
# 1. match on all three fields (board book top level, section title, primary strategy)
# 2. match on board book top level and section title
# 3. match on board book top level and primary strategy
# 4. match on board book top level only

def apply_mapping(row):
    """
    apply mapping rules to a single row by matching against the mapping table
    returns tuple of (program, strategy, substrategy)
    """
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
    # this handles cases like CLIMATE where section title varies but primary strategy is key
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

df.to_csv(output_file, index=False, encoding='utf-8-sig')
print(f"\noutput saved to: {output_file}")
print("\nnote: output file uses utf-8 encoding with properly normalized text")