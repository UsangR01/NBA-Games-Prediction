"""
Main aim of this section: 
1. Data Preparation 
2. Identify top performing players necessary to create the combined PER feature (Big 3) for each team
"""


import warnings
warnings.filterwarnings('ignore')
import os
import pandas as pd

pd.set_option('display.max_columns', None) # so we can see all columns in a wide DataFrame
# pd.set_option('display.max_rows', None)

# Load the data that shows player participation in each game
gameLineup = pd.read_csv("data/parsed_csvs/gameLineup_csv/gameLineup.csv", index_col=0)
playerStats = pd.read_csv("data/parsed_csvs/playerStats_csv/combined_playerStats/playerStats_running.csv")

# Creating a feature to determine minutes played per game for each player
playerStats['MPG'] = round(playerStats['MP'] / playerStats['G'], 2)

# Create a dataframe with some selected features
playerStats_df = playerStats[["Player", "Tm", "MPG", "PER", "WS/48", "Season Year"]]

# To remove the asterisk character (*) from the "Player" column in the playerStats_df DataFrame, you can use the str.replace() method as follows: NB, in pandas, asterisk can have a meaning as a regular expression, hence we equate the regex=False 
playerStats_df = playerStats_df.copy()
playerStats_df["Player"] = playerStats_df["Player"].str.replace("*", "", regex=False)

# Now, we want only their total for that year, deleting other rows. So we write a function to iterate through each group
def single_row(df):
    if df.shape[0]==1:
        return df
    else:
        row = df[df["Tm"]=="TOT"]
        row["Tm"] = df.iloc[-1,:]["Tm"]   # Since TOT is not a valid team, we replace TOT with the name of the last team the player played in
        return row
    
# We copy the groupby, and use the apply method to apply this function to each group
playerStats_df = playerStats_df.groupby(["Player", "Season Year"]).apply(single_row)

# We now have multilevel indexing from the groupby (Player, Year and the original indexing). Dropping the Player and Year multi-index:
playerStats_df.index = playerStats_df.index.droplevel()
playerStats_df.index = playerStats_df.index.droplevel()

# Creating a dataframe to identify top 5 key players per team
teamGroup = playerStats_df.groupby(["Tm", "Season Year"], group_keys=False)

def sort_Top5_players_by_per(group):
    group_above_26 = group[group['MPG'] >= 26]  # Filter players with MPG >= 26
    group_between_18_26 = group[(group['MPG'] >= 18) & (group['MPG'] < 26)]  # Filter players with MPG between 18 and 26

    # Select top players from group_above_26 first
    top_players = group_above_26.sort_values("WS/48", ascending=False).head(5)
    
    # Calculate how many more players are needed to reach 5
    remaining_count = 5 - len(top_players)
    
    if remaining_count > 0:
        # If needed, add players from group_between_18_26
        additional_players = group_between_18_26.sort_values("WS/48", ascending=False).head(remaining_count)
        top_players = pd.concat([top_players, additional_players])
    
    # Recheck if we still need more players (in case both groups didn't add up to 5 players)
    remaining_count = 5 - len(top_players)
    
    if remaining_count > 0:
        # Fallback: Select remaining players from the entire group based on WS/48
        additional_players = group[~group.index.isin(top_players.index)].sort_values("WS/48", ascending=False).head(remaining_count)
        top_players = pd.concat([top_players, additional_players])
    
    # Add new columns for PER of top players
    player_columns = ['Top1', 'Top2', 'Top3', 'Top4', 'Top5']  # Specify the player name columns
    per_columns = ['Top1_PER', 'Top2_PER', 'Top3_PER', 'Top4_PER', 'Top5_PER']  # New columns for PER
    
    # Construct the final result with top players' names and their PER values
    concatenated_stats = top_players.groupby(['Tm', 'Season Year'])['Player'].apply(list).apply(pd.Series).rename(columns=lambda x: player_columns[x]).reset_index().reset_index(drop=True)
    
    # Add PER values to the new columns
    for i, col in enumerate(player_columns):
        player_names = concatenated_stats[col]
        per_values = group[group['Player'].isin(player_names)]['PER'].values
        concatenated_stats[per_columns[i]] = per_values

    return concatenated_stats

top_five_players_per_team = teamGroup.apply(sort_Top5_players_by_per)

# Get the column names of the dataframe
column_names = top_five_players_per_team.columns.tolist()

# Remove 'Tm' and 'Season Year' columns from the list
column_names.remove('Tm')
column_names.remove('Season Year')

# Insert 'Tm' and 'Season Year' columns at the desired position
desired_position = len(column_names)  # Last position
column_names.insert(desired_position, 'Tm')
column_names.insert(desired_position + 1, 'Season Year')

# Reorder the columns in the dataframe
top_five_players_per_team = top_five_players_per_team[column_names]
top_five_players_per_team = top_five_players_per_team.rename(columns={'Tm': 'Team'})

# Merge the two dataframes based on team and season-year columns
merged_df = gameLineup.merge(top_five_players_per_team, on=['Team', 'Season Year'], how='left')

# Create new columns
merged_df['Big5'] = 0
merged_df['Big4'] = 0
merged_df['Big3'] = 0
merged_df['Big2'] = 0
merged_df['Big1'] = 0

# Iterate over the rows
for index, row in merged_df.iterrows():
    top_players = [row['Top1'], row['Top2'], row['Top3'], row['Top4'], row['Top5']]
    players_in_game = [row['Player 1'], row['Player 2'], row['Player 3'], row['Player 4'], row['Player 5'], row['Player 6'], row['Player 7'], row['Player 8'], row['Player 9'], row['Player 10'], row['Player 11'], row['Player 12'], row['Player 13'], row['Player 14'], row['Player 15']]

    if all(player in players_in_game for player in top_players):
        merged_df.at[index, 'Big5'] = 1
    elif len(set(players_in_game).intersection(top_players)) == 4:
        merged_df.at[index, 'Big4'] = 1
    elif len(set(players_in_game).intersection(top_players)) == 3:
        merged_df.at[index, 'Big3'] = 1
    elif len(set(players_in_game).intersection(top_players)) == 2:
        merged_df.at[index, 'Big2'] = 1
    elif len(set(players_in_game).intersection(top_players)) == 1:
        merged_df.at[index, 'Big1'] = 1

# Create new column 'PER_Combined'
merged_df['PER_Combined'] = 0

# Iterate over the rows
for index, row in merged_df.iterrows():
    top_players = [row['Top1'], row['Top2'], row['Top3'], row['Top4'], row['Top5']]
    players_in_game = [row[f'Player {i}'] for i in range(1, 16)]

    # Get the common players between the top players and players in the game
    common_players = set(top_players).intersection(players_in_game)

    # Sum the PER values of the common players in the game roster
    per_values = [row[f'Top{i}_PER'] for i in range(1, 6) if row[f'Top{i}'] in common_players]
    merged_df.at[index, 'PER_Combined'] = sum(per_values)
        
# Print the resulting dataframe
Big5_df = merged_df[["Team", "Season Year", 'Top1', 'Top2', 'Top3', 'Top4', 'Top5', 'Top1_PER', 'Top2_PER', 'Top3_PER', 'Top4_PER', 'Top5_PER', 'Big5', 'Big4', 'Big3', 'Big2', 'Big1', 'PER_Combined']]

# Drop all alternate rows from Big5_df and create a new DataFrame called opp_teamStats
opp_teamStats = Big5_df.iloc[1::2].reset_index(drop=True)
# Rename columns with "_opp" suffix (excluding 'Season Year')
opp_teamStats.rename(columns={col: f'{col}_opp' for col in opp_teamStats.columns if col != 'Season Year'}, inplace=True)

# Drop all alternate rows from Big5_df and create a new DataFrame called opp_teamStats
main_teamStats = Big5_df.iloc[::2].reset_index(drop=True)
# Rename columns with "_opp" suffix (excluding 'Season Year')
main_teamStats.rename(columns={col: f'{col}_opp' for col in main_teamStats.columns if col != 'Season Year'}, inplace=True)

main_df = pd.concat([main_teamStats, opp_teamStats], axis=1)
opp_df = pd.concat([opp_teamStats, main_teamStats], axis=1)

# Step 1: Create an array to alternate between main_df and opp_df rows
combined_rows = []

# Step 2: Get the maximum number of rows between main_df and opp_df
max_rows = max(len(main_df), len(opp_df))

# Step 3: Loop through the range of rows
for i in range(max_rows):
    # Check if there's a row in main_df and add it to combined_rows
    if i < len(main_df):
        combined_rows.append(main_df.iloc[i])
    # Check if there's a row in opp_df and add it to combined_rows
    if i < len(opp_df):
        combined_rows.append(opp_df.iloc[i])

# Step 4: Create the concatenated dataframe
Big5_bothTeams = pd.concat(combined_rows, axis=1).transpose()

# If you want to reset the index, uncomment the following line
Big5_bothTeams.reset_index(drop=True, inplace=True)

# Step 1: Remove the "_opp" suffix from the column names of the first 18 columns
Big5_bothTeams.columns = [col.replace("_opp", "") if i < 18 else col for i, col in enumerate(Big5_bothTeams.columns)]
Big5_bothTeams

"""
Loading and combine the nba_games.csv dataset with the Big5_bothTeams dataset...
"""
game_df = pd.read_csv("data/parsed_csvs/scores_csv/nba_games_running.csv", index_col=0)
combined_df = pd.concat([game_df, Big5_bothTeams], axis=1)

# Convert the 'date' column to datetime format
combined_df['date'] = pd.to_datetime(combined_df['date'], errors='coerce')

# Now, we sort the DataFrame by the 'date' column
combined_df = combined_df.sort_values("date")

combined_df = combined_df.reset_index(drop=True)

# Dropping specified columns
# Mostly duplicate columns like, pts and pts_opp which are replica columns of total and total_opp
columns_to_drop = ['pts', 'pts_opp', 'gmsc', 'gmsc_opp', 'gmsc_max', 'gmsc_max_opp', '+/-', '+/-_opp', "mp.1", "mp_opp", "mp_opp.1", "mp_max", "mp_max.1", 'mp_max_opp', 'mp_max_opp.1', "index_opp", "Team", "Season Year", 'Big5', 'Big4', 'Big3', 'Big2', 'Big1', 'Team_opp', 'Big5_opp', 'Big4_opp', 'Big3_opp', 'Big2_opp', 'Big1_opp']
combined_df = combined_df.drop(columns=columns_to_drop)

# Convert specified columns to float, coercing errors to NaN
combined_df['PER_Combined'] = pd.to_numeric(combined_df['PER_Combined'], errors='coerce')
combined_df['PER_Combined_opp'] = pd.to_numeric(combined_df['PER_Combined_opp'], errors='coerce')

# Filling missing values with median imputation
# Loop over each column in the DataFrame
for col in combined_df.columns:
    if combined_df[col].dtype in ['int64', 'float64']:  # Check if the column is numeric
        median_value = combined_df[col].median()  # Calculate median
        combined_df[col].fillna(median_value, inplace=True)  # Fill missing values with median

# nulls = pd.isnull(combined_df).sum().sort_values(ascending=False)
# nulls = nulls[nulls > 0]
# print(nulls)


# Drop missing values
combined_df.dropna(axis=1, inplace=True)

# Replace 'CHO' with 'CHA' in the 'team' column of combined_df
combined_df['team'] = combined_df['team'].replace('CHO', 'CHA')
combined_df['team_opp'] = combined_df['team_opp'].replace('CHO', 'CHA')


"""
Saving out the cleaned dataset
"""
output_dir = "data/preprocessed_cleaned_csv"
os.makedirs(output_dir, exist_ok=True)

combined_df.to_csv("data/preprocessed_cleaned_csv/fullGame_stats.csv")