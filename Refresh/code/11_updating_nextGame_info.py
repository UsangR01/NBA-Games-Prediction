import pandas as pd
pd.set_option('display.max_columns', None) # so we can see all columns in a wide DataFrame
import warnings
warnings.filterwarnings('ignore')


fullGame_df = pd.read_csv("data/feature_engineered_csv/fullGame_with_nextGame_features.csv")
# print(fullGame_df[["team_x", "team_opp_next_x", "PER_Combined_opp_next_x", "team_y", "team_opp_next_y", "PER_Combined_opp_next_y", "date_next"]])

# Identify rows where "Not Played" appears in any of the next game columns
not_played_indices = fullGame_df[
    (fullGame_df["home_next_x"] == "Not Played") |
    (fullGame_df["team_opp_next_x"] == "Not Played") |
    (fullGame_df["date_next"] == "Not Played") |
    (fullGame_df["PER_Combined_opp_next_x"] == "Not Played") |
    (fullGame_df["elo_rating_opp_next_x"] == "Not Played") |
    (fullGame_df["head_to_head_win_ratio_next_x"] == "Not Played")
].index

# Print the list of indices
print("Indices with 'Not Played':", not_played_indices.tolist())


# """
# This are the last games for each team where the next games are not known
# """
# target_2_rows = fullGame_df[fullGame_df["target"] == 2]
# print(target_2_rows)

# nulls = pd.isnull(fullGame_df).sum().sort_values(ascending=False)
# nulls = nulls[nulls > 0]
# print(nulls)