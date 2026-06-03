import json
import os


def convert_inches_to_meters(json_file_path, output_file_path):
    """
    Takes in a path to an april tag layout JSON file and converts all translation values from inches to meters.

    Args:
        json_file_path (str): Path to the input JSON file.
        output_file_path (str): Path to save the converted JSON file.
    """
    INCHES_TO_METERS = 0.0254

    # Resolve paths relative to the script's directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    json_file_path = os.path.join(script_dir, json_file_path)
    output_file_path = os.path.join(script_dir, output_file_path)

    # Read the JSON file
    with open(json_file_path, "r") as file:
        data = json.load(file)

    # Iterate through the tags and convert translation values
    for tag in data.get("tags", []):
        translation = tag.get("pose", {}).get("translation", {})
        if translation:
            translation["x"] *= INCHES_TO_METERS
            translation["y"] *= INCHES_TO_METERS
            translation["z"] *= INCHES_TO_METERS

    # Save the updated JSON to the output file
    with open(output_file_path, "w") as file:
        json.dump(data, file, indent=2)

    print(f"Converted JSON saved to {output_file_path}")


# Example usage
# Replace 'input.json' and 'output.json' with your file paths
# convert_inches_to_meters('input.json', 'output.json')

convert_inches_to_meters(
    "unofficialWeldedAprilTagLayout.json", "field_calibration.json"
)
