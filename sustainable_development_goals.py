"""The 17 UN Sustainable Development Goals, as used by OGCR.

Transcribed from the "SDGs enum" sheet of `SDG_enum.xlsx`. Each row is
(sustainable_development_goal_id, goal number, name, icon url). The icon url is
written to the entity's `sustainable_development_goal_link` field; the goal
number goes to `sustainable_development_goal_number`, which the entity does
not define yet, so it is skipped (with a warning) until the sheet adds it.
"""

# (id, number, name, icon_url)
SUSTAINABLE_DEVELOPMENT_GOALS = [
    ('NO_POVERTY', 'GOAL_1', 'No Poverty', 'https://open-sdg.github.io/sdg-translations/assets/img/goals/en/1.png'),
    ('ZERO_HUNGER', 'GOAL_2', 'Zero Hunger', 'https://open-sdg.github.io/sdg-translations/assets/img/goals/en/2.png'),
    ('GOOD_HEALTH_WELL_BEING', 'GOAL_3', 'Good Health and Well-being', 'https://open-sdg.github.io/sdg-translations/assets/img/goals/en/3.png'),
    ('QUALITY_EDUCATION', 'GOAL_4', 'Quality Education', 'https://open-sdg.github.io/sdg-translations/assets/img/goals/en/4.png'),
    ('GENDER_EQUALITY', 'GOAL_5', 'Gender Equality', 'https://open-sdg.github.io/sdg-translations/assets/img/goals/en/5.png'),
    ('CLEAN_WATER_SANITATION', 'GOAL_6', 'Clean Water and Sanitation', 'https://open-sdg.github.io/sdg-translations/assets/img/goals/en/6.png'),
    ('AFFORDABLE_CLEAN_ENERGY', 'GOAL_7', 'Affordable and Clean Energy', 'https://open-sdg.github.io/sdg-translations/assets/img/goals/en/7.png'),
    ('DECENT_WORK_ECONOMIC_GROWTH', 'GOAL_8', 'Decent Work & Economic Growth', 'https://open-sdg.github.io/sdg-translations/assets/img/goals/en/8.png'),
    ('INDUSTRY_INNOVATION_INFRASTRUCTURE', 'GOAL_9', 'Industry, Innovation & Infrastructure', 'https://open-sdg.github.io/sdg-translations/assets/img/goals/en/9.png'),
    ('REDUCED_INEQUALITIES', 'GOAL_10', 'Reduced Inequalities', 'https://open-sdg.github.io/sdg-translations/assets/img/goals/en/10.png'),
    ('SUSTAINABLE_CITIES_COMMUNITIES', 'GOAL_11', 'Sustainable Cities & Communities', 'https://open-sdg.github.io/sdg-translations/assets/img/goals/en/11.png'),
    ('RESPONSIBLE_CONSUMPTION_PRODUCTION', 'GOAL_12', 'Responsible Consumption & Production', 'https://open-sdg.github.io/sdg-translations/assets/img/goals/en/12.png'),
    ('CLIMATE_ACTION', 'GOAL_13', 'Climate Action', 'https://open-sdg.github.io/sdg-translations/assets/img/goals/en/13.png'),
    ('LIFE_BELOW_WATER', 'GOAL_14', 'Life Below Water', 'https://open-sdg.github.io/sdg-translations/assets/img/goals/en/14.png'),
    ('LIFE_ON_LAND', 'GOAL_15', 'Life on Land', 'https://open-sdg.github.io/sdg-translations/assets/img/goals/en/15.png'),
    ('PEACE_JUSTICE_STRONG_INSTITUTIONS', 'GOAL_16', 'Peace, Justice & Strong Institutions', 'https://open-sdg.github.io/sdg-translations/assets/img/goals/en/16.png'),
    ('PARTNERSHIPS_FOR_THE_GOALS', 'GOAL_17', 'Partnerships for the Goals', 'https://open-sdg.github.io/sdg-translations/assets/img/goals/en/17.png'),
]
