import requests
import csv
import gitlab
import re

# Replace with your actual GitLab access token and parent group ID
PRIVATE_TOKEN = 'glpat-XYZ'  # Replace with your token
PARENT_GROUP_ID = '11982363'  # The top-level group ID
GITLAB_URL = 'https://gitlab.com/api/v4'

# Headers for API requests
headers = {'PRIVATE-TOKEN': PRIVATE_TOKEN}

# Function to recursively get all projects in a group (including subgroups)
def get_all_projects_in_group(group_id):
    projects = []
    page = 1
    per_page = 100

    # Fetch projects in the group
    while True:
        response = requests.get(f'{GITLAB_URL}/groups/{group_id}/projects', headers=headers, params={'per_page': per_page, 'page': page})
        if response.status_code == 200:
            projects_in_group = response.json()
            if not projects_in_group:
                break
            projects.extend(projects_in_group)
            page += 1
        else:
            print(f"Error fetching projects for group ID: {group_id}, Status Code: {response.status_code}")
            return projects

    # Fetch subgroups
    page = 1
    while True:
        response = requests.get(f'{GITLAB_URL}/groups/{group_id}/subgroups', headers=headers, params={'per_page': per_page, 'page': page})
        if response.status_code == 200:
            subgroups = response.json()
            if not subgroups:
                break
            for subgroup in subgroups:
                # Recursively fetch projects in subgroups
                projects.extend(get_all_projects_in_group(subgroup['id']))
            page += 1
        else:
            print(f"Error fetching subgroups for group ID: {group_id}, Status Code: {response.status_code}")
            break
    return projects

# Function to check if a project has a CI/CD pipeline
def check_cicd_pipeline(project_id):
    # Check if there are any pipelines associated with the project
    response = requests.get(f'{GITLAB_URL}/projects/{project_id}/pipelines', headers=headers)
    if response.status_code == 200:
        pipelines = response.json()
        if len(pipelines) > 0:
            return "Yes"
        else:
            return "No"
    else:
        print(f"Error checking pipelines for project ID: {project_id}, Status Code: {response.status_code}")
        return "No"

# Function to get the last commit date of a project
def get_last_commit_date(project_id):
    response = requests.get(f'{GITLAB_URL}/projects/{project_id}/repository/commits', headers=headers, params={'per_page': 1})
    if response.status_code == 200:
        commits = response.json()
        if commits:
            return commits[0]['created_at']
    return "No commits"

# Function to check if Terraform files in a project use modules by looking for the 'source' keyword
def check_terraform_modules(project_id):
    # Fetch the list of files in the project repository
    response = requests.get(f'{GITLAB_URL}/projects/{project_id}/repository/tree', headers=headers, params={'recursive': True})
    if response.status_code == 200:
        files = response.json()
        # Filter for Terraform files
        terraform_files = [file for file in files if file['name'].endswith('.tf')]
        if not terraform_files:
            return "No"

        # Check for 'source' keyword in each Terraform file
        for file in terraform_files:
            file_path = file['path']
            file_response = requests.get(f'{GITLAB_URL}/projects/{project_id}/repository/files/{file_path}/raw', headers=headers, params={'ref': 'master'})
            if file_response.status_code == 200:
                content = file_response.text
                # Check if the file contains the word "source"
                if re.search(r'\bsource\b', content):
                    return "Yes"
    return "No"

# Write the data to a CSV file
def write_to_csv(projects_data, filename='projects_with_cicd.csv'):
    with open(filename, 'w', newline='') as csvfile:
        fieldnames = ['Project Name', 'Project Path', 'Has CI/CD Pipeline', 'Last Commit Date', 'Uses Terraform Modules']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        for project in projects_data:
            writer.writerow({
                'Project Name': project['name'],
                'Project Path': project['path_with_namespace'],
                'Has CI/CD Pipeline': project['has_cicd'],
                'Last Commit Date': project['last_commit'],
                'Uses Terraform Modules': project['uses_terraform_modules']
            })

# Main function
def main():
    print("Fetching all projects and subgroups recursively...")
    projects = get_all_projects_in_group(PARENT_GROUP_ID)
    projects_data = []

    if not projects:
        print("No projects found.")
        return

    print(f"Found {len(projects)} projects.")

    # Process each project
    for project in projects:
        print(f"Processing project: {project['name']} (ID: {project['id']})")
        has_cicd = check_cicd_pipeline(project['id'])
        last_commit = get_last_commit_date(project['id'])
        uses_terraform_modules = check_terraform_modules(project['id'])
        # Ignore projects that don't use Terraform modules
        if uses_terraform_modules == "No":
            continue
        projects_data.append({
            'name': project['name'],
            'path_with_namespace': project['path_with_namespace'],
            'has_cicd': has_cicd,
            'last_commit': last_commit,
            'uses_terraform_modules': uses_terraform_modules
        })

    # Write the data to a CSV file
    write_to_csv(projects_data)
    print(f"Data written to 'projects_with_cicd.csv'")

if __name__ == '__main__':
    main()
