"""MyFitnessPal module manifest — tool definitions."""

from shared.schemas.tools import ModuleManifest, ToolDefinition, ToolParameter

MANIFEST = ModuleManifest(
    module_name="myfitnesspal",
    description="Retrieve nutrition, meal diary, and body measurement data from MyFitnessPal.",
    tools=[
        ToolDefinition(
            name="myfitnesspal.get_day",
            description=(
                "Get the food diary for a specific date from MyFitnessPal. "
                "Returns all meals (breakfast, lunch, dinner, snacks) with individual "
                "food entries and nutritional totals (calories, carbs, fat, protein, "
                "sodium, sugar). Also includes daily goals and completion status. "
                "Defaults to today."
            ),
            parameters=[
                ToolParameter(
                    name="date",
                    type="string",
                    description="Date in YYYY-MM-DD format (default: today)",
                    required=False,
                ),
            ],
            required_permission="user",
        ),
        ToolDefinition(
            name="myfitnesspal.get_measurements",
            description=(
                "Get body measurements from MyFitnessPal over a date range. "
                "Returns measurement values (e.g. weight, body fat, waist) for "
                "each recorded date. Defaults to the last 30 days of weight data."
            ),
            parameters=[
                ToolParameter(
                    name="measurement",
                    type="string",
                    description=(
                        "Type of measurement to retrieve, e.g. 'Weight', 'Body Fat', "
                        "'Waist', 'Neck', 'Hips' (default: 'Weight')"
                    ),
                    required=False,
                ),
                ToolParameter(
                    name="start_date",
                    type="string",
                    description="Start date in YYYY-MM-DD format (default: 30 days ago)",
                    required=False,
                ),
                ToolParameter(
                    name="end_date",
                    type="string",
                    description="End date in YYYY-MM-DD format (default: today)",
                    required=False,
                ),
            ],
            required_permission="user",
        ),
        ToolDefinition(
            name="myfitnesspal.get_report",
            description=(
                "Get a nutrition or fitness report from MyFitnessPal over a date range. "
                "Returns daily values for the requested metric. "
                "Common report names: 'Net Calories', 'Total Calories', 'Carbs', "
                "'Fat', 'Protein', 'Fiber', 'Sugar'. "
                "Categories: 'Nutrition' or 'Fitness'. "
                "Defaults to Net Calories over the last 7 days."
            ),
            parameters=[
                ToolParameter(
                    name="report_name",
                    type="string",
                    description="Report metric name, e.g. 'Net Calories', 'Protein', 'Fat' (default: 'Net Calories')",
                    required=False,
                ),
                ToolParameter(
                    name="report_category",
                    type="string",
                    description="Report category: 'Nutrition' or 'Fitness' (default: 'Nutrition')",
                    required=False,
                ),
                ToolParameter(
                    name="start_date",
                    type="string",
                    description="Start date in YYYY-MM-DD format (default: 7 days ago)",
                    required=False,
                ),
                ToolParameter(
                    name="end_date",
                    type="string",
                    description="End date in YYYY-MM-DD format (default: today)",
                    required=False,
                ),
            ],
            required_permission="user",
        ),
        ToolDefinition(
            name="myfitnesspal.search_food",
            description=(
                "Search the MyFitnessPal food database for a food item. "
                "Returns matching food items with their nutritional information "
                "and serving sizes."
            ),
            parameters=[
                ToolParameter(
                    name="query",
                    type="string",
                    description="Food search query, e.g. 'chicken breast', 'banana'",
                ),
            ],
            required_permission="user",
        ),
    ],
)
