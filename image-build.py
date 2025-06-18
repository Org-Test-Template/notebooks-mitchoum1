import subprocess
import time
import os
import json

# Helper function to convert bytes to human-readable format (KB, MB, GB)
def bytes_to_human_readable(num_bytes):
    """Converts a number of bytes into a human-readable string (KB, MB, GB)."""
    if num_bytes is None or not isinstance(num_bytes, (int, float)):
        return "N/A"
    
    for unit in ['Bytes', 'KB', 'MB', 'GB', 'TB']:
        if num_bytes < 1024.0:
            return f"{num_bytes:.2f} {unit}"
        num_bytes /= 1024.0
    return f"{num_bytes:.2f} PB" # For extremely large sizes


# --- Get inputs from the user ---
# Prompt the user for the tag name
tag_name = input("Enter the tag name for the Podman image (e.g., 'minimal'): ")
# Prompt the user for the Dockerfile path
dockerfile_path = input("Enter the full path to the Dockerfile (e.g., 'jupyter/minimal/ubi9-python-3.11/Dockerfile.cpu'): ")
# Prompt the user for the build context path
build_context = input("Enter the build context path (e.g., '.' for current directory): ")
# Prompt the user for the --no-cache option
use_no_cache_input = input("Use --no-cache for builds? (y/n): ").lower().strip()
use_no_cache = use_no_cache_input == 'y'
# Prompt the user for the cleanup option
perform_cleanup_input = input("Perform 'podman system prune -f' after each build? (y/n): ").lower().strip()
perform_cleanup = perform_cleanup_input == 'y'


# The base command for podman build
base_build_command_args = [
    "podman",
    "build"
]

# Add --no-cache if the user opted for it
if use_no_cache:
    base_build_command_args.append("--no-cache")

# Add the rest of the build arguments
base_build_command_args.extend([
    "-t",
    tag_name,  # Use the user-provided tag name
    "-f",
    dockerfile_path,  # Use the user-provided Dockerfile path
    build_context  # Use the user-provided build context
])

# Command for cleaning up Podman system
cleanup_command_args = ["podman", "system", "prune", "-f"]

# Command to get image size using 'podman image inspect'
# This command will directly output the size in bytes as an integer string
# Note: tag_name will be appended to this list later in the loop
base_image_inspect_command_args = ["podman", "image", "inspect", "--format", "{{.Size}}"]


num_runs = 10
run_times = []
image_sizes_human_readable = [] # To store image sizes as human-readable strings for display
numerical_image_sizes_bytes = [] # To store image sizes as raw bytes (integers) for calculation

print(f"\nAttempting to run command: {' '.join(base_build_command_args)}")
print(f"This command will be executed {num_runs} times, and the duration of each run will be tracked.")
if perform_cleanup:
    print("A 'podman system prune -f' will be executed after each build attempt to free up space.")
else:
    print("Cleanup after each build is disabled as per your choice.")

print("Image size will be displayed after each successful build.")
print("\n--- Starting Execution ---")

for i in range(num_runs):
    print(f"\n--- Run {i+1}/{num_runs} ---")
    current_build_successful = False
    start_time = time.time()
    try:
        print("Starting Podman build...")
        build_result = subprocess.run(
            base_build_command_args,
            check=True, # Raise CalledProcessError if the command returns a non-zero exit code
            capture_output=True,
            text=True
        )
        end_time = time.time()
        duration = end_time - start_time
        run_times.append(duration)
        print(f"Command finished successfully in {duration:.2f} seconds.")
        current_build_successful = True # Mark build as successful

    except FileNotFoundError:
        end_time = time.time()
        duration = end_time - start_time
        run_times.append(duration)
        print(f"Error: The command '{base_build_command_args[0]}' was not found.")
        print("Please ensure 'podman' is installed and accessible in your system's PATH.")
        break # Break if podman itself isn't found
    except subprocess.CalledProcessError as e:
        end_time = time.time()
        duration = end_time - start_time
        run_times.append(duration)
        print(f"Command failed with exit code {e.returncode} in {duration:.2f} seconds.")
        print(f"STDOUT:\n{e.stdout}")
        print(f"STDERR:\n{e.stderr}")
    except Exception as e:
        end_time = time.time()
        duration = end_time - start_time
        run_times.append(duration)
        print(f"An unexpected Python error occurred during build: {e}")
        print(f"Error occurred after {duration:.2f} seconds.")

    # --- Get image size if build was successful ---
    if current_build_successful:
        try:
            print(f"Retrieving size for image '{tag_name}'...")
            # Construct the full image inspect command
            image_inspect_command_for_run = base_image_inspect_command_args + [tag_name]
            
            # Run podman image inspect to get the size
            size_result = subprocess.run(
                image_inspect_command_for_run,
                check=True,
                capture_output=True,
                text=True
            )
            # The output should directly be the size string (in bytes)
            raw_image_size_str = size_result.stdout.strip()
            
            try:
                raw_image_size_bytes = int(raw_image_size_str)
                numerical_image_sizes_bytes.append(raw_image_size_bytes)
                found_image_size_human = bytes_to_human_readable(raw_image_size_bytes)
                image_sizes_human_readable.append(found_image_size_human)
                print(f"Image '{tag_name}' size: {found_image_size_human}")
            except ValueError:
                print(f"Warning: Could not parse image size '{raw_image_size_str}' to a number.")
                image_sizes_human_readable.append(f"Invalid: {raw_image_size_str}")
                numerical_image_sizes_bytes.append(None) # Append None or 0 to indicate failure to parse

        except subprocess.CalledProcessError as e:
            print(f"Error getting image size (exit code {e.returncode}):")
            print(f"STDOUT:\n{e.stdout}")
            print(f"STDERR:\n{e.stderr}")
            image_sizes_human_readable.append("Error")
            numerical_image_sizes_bytes.append(None)
        except Exception as e:
            print(f"An unexpected Python error occurred while getting image size: {e}")
            image_sizes_human_readable.append("Error")
            numerical_image_sizes_bytes.append(None)
    else:
        # If build wasn't successful, append placeholders
        image_sizes_human_readable.append("Failed Build")
        numerical_image_sizes_bytes.append(None)


    # --- Clean up after each run (optional) ---
    if perform_cleanup:
        print("\nAttempting to clean up Podman system space...")
        try:
            cleanup_result = subprocess.run(
                cleanup_command_args,
                check=False, # Do not raise an error if cleanup fails; we still want to continue with builds
                capture_output=True,
                text=True
            )
            if cleanup_result.returncode == 0:
                print("Podman system cleanup successful.")
            else:
                print(f"Podman system cleanup failed with exit code {cleanup_result.returncode}.")
                print(f"Cleanup STDOUT:\n{cleanup_result.stdout}")
                print(f"Cleanup STDERR:\n{cleanup_result.stderr}")
        except FileNotFoundError:
            print(f"Error: The cleanup command '{cleanup_command_args[0]}' was not found.")
            print("Please ensure 'podman' is installed and accessible in your system's PATH.")
        except Exception as e:
            print(f"An unexpected error occurred during cleanup: {e}")
    else:
        print("\nSkipping Podman system cleanup as requested.")


print("\n--- Summary of Run Times and Image Sizes ---")
# Use the human-readable sizes for individual run display
min_len = min(len(run_times), len(image_sizes_human_readable))
for i in range(min_len):
    print(f"Run {i+1}: Time = {run_times[i]:.2f} seconds, Image Size = {image_sizes_human_readable[i]}")

# Handle cases where one list might be longer than the other (e.g., if a build broke early)
if len(run_times) > min_len:
    for i in range(min_len, len(run_times)):
        print(f"Run {i+1}: Time = {run_times[i]:.2f} seconds, Image Size = Not Recorded (Error during size retrieval)")
if len(image_sizes_human_readable) > min_len:
    for i in range(min_len, len(image_sizes_human_readable)):
        print(f"Run {i+1}: Image Size = {image_sizes_human_readable[i]}, Time = Not Recorded (Error during build)")


if run_times:
    total_time = sum(run_times)
    if len(run_times) > 0:
        average_time = total_time / len(run_times)
        print(f"\nTotal time for {len(run_times)} runs: {total_time:.2f} seconds")
        print(f"Average time per run: {average_time:.2f} seconds")
    else:
        print("No run times recorded.")
else:
    print("No runs were completed.")

# --- Calculate and display average image size ---
valid_numerical_sizes = [s for s in numerical_image_sizes_bytes if s is not None]
if valid_numerical_sizes:
    total_image_bytes = sum(valid_numerical_sizes)
    average_image_bytes = total_image_bytes / len(valid_numerical_sizes)
    print(f"\nAverage image size across {len(valid_numerical_sizes)} successful builds: {bytes_to_human_readable(average_image_bytes)}")
else:
    print("\nNo valid image sizes were recorded to calculate an average.")