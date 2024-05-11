#!/bin/bash

# Color variables
COLOR_RESET='\033[0m'       # Reset color
COLOR_BOLD='\033[1m'        # Bold
COLOR_RED='\033[0;31m'      # Red
COLOR_GREEN='\033[0;32m'    # Green
COLOR_YELLOW='\033[0;33m'   # Yellow

# Function to add a password
add_password() {
    echo "Enter the name of the service:"
    read -p "$(echo -e ${COLOR_BOLD}Service:${COLOR_RESET}) " service
    echo "Enter your username/email:"
    read -p "$(echo -e ${COLOR_BOLD}Username/Email:${COLOR_RESET}) " username
    echo "Enter your password:"
    read -s -p "$(echo -e ${COLOR_BOLD}Password:${COLOR_RESET}) " password
    echo "$service:$username:$password" >> passwords.txt
    echo -e "${COLOR_GREEN}Password added for $service.${COLOR_RESET}"
}

# Function to list all saved passwords
list_passwords() {
    echo -e "${COLOR_BOLD}Saved Passwords:${COLOR_RESET}"
    cat passwords.txt | cut -d':' -f1
}

# Function to retrieve a password
get_password() {
    echo "Enter the name of the service:"
    read -p "$(echo -e ${COLOR_BOLD}Service:${COLOR_RESET}) " service
    password=$(grep "^$service:" passwords.txt | cut -d':' -f3)
    if [ -z "$password" ]; then
        echo -e "${COLOR_RED}Password not found for $service.${COLOR_RESET}"
    else
        echo -e "${COLOR_BOLD}Password for $service:${COLOR_RESET}"
        echo "$password"
    fi
}

# Main menu
while true; do
    echo -e "${COLOR_BOLD}Password Manager${COLOR_RESET}"
    echo -e "${COLOR_YELLOW}1. ${COLOR_RESET}${COLOR_BOLD}Add Password${COLOR_RESET}"
    echo -e "${COLOR_YELLOW}2. ${COLOR_RESET}${COLOR_BOLD}List Passwords${COLOR_RESET}"
    echo -e "${COLOR_YELLOW}3. ${COLOR_RESET}${COLOR_BOLD}Get Password${COLOR_RESET}"
    echo -e "${COLOR_YELLOW}4. ${COLOR_RESET}${COLOR_BOLD}Exit${COLOR_RESET}"
    read -p "$(echo -e ${COLOR_BOLD}Enter your choice:${COLOR_RESET}) " choice

    case $choice in
        1) add_password;;
        2) list_passwords;;
        3) get_password;;
        4) echo "Exiting..."
           break;;
        *) echo -e "${COLOR_RED}Invalid choice. Please try again.${COLOR_RESET}";;
    esac
done

