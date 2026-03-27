"""Load and validate contact information for User-Agent disclosure.

This module provides a centralized way to load contact information that must be
provided by the user to comply with Wikimedia service policies. The contact file
is not part of the repository and must be created locally by each user or deployment.
"""
from __future__ import annotations

import json
from pathlib import Path


def find_contact_file(start: Path = None) -> Path:
	"""Locate the .contact-info.json file.
	
	Searches up from the start directory (or current directory) until it finds
	a .contact-info.json file in the repository root.
	
	Args:
		start: Starting directory for search. Defaults to current directory.
	
	Returns:
		Path to the .contact-info.json file.
	
	Raises:
		FileNotFoundError: If .contact-info.json is not found in the repository.
	"""
	if start is None:
		start = Path.cwd()
	
	current = start.resolve()
	
	# Search upward up to 10 levels to find the repo root and contact file
	for _ in range(10):
		contact_file = current / ".contact-info.json"
		if contact_file.exists():
			return contact_file
		
		# Check if we're at a filesystem boundary
		if current.parent == current:
			break
		current = current.parent
	
	# Not found - provide helpful error message
	raise FileNotFoundError(
		"\n"
		"Contact information file is required but not found.\n"
		"\n"
		"To comply with Wikimedia service policies, you must create a .contact-info.json file\n"
		"in the repository root with your contact information. This file should not be\n"
		"committed to version control.\n"
		"\n"
		"Steps to set up contact information:\n"
		"1. Copy the template file to your repository root:\n"
		"   cp .contact-info.json.example .contact-info.json\n"
		"\n"
		"2. Edit .contact-info.json and fill in your email address:\n"
		"   {\n"
		"     \"email\": \"your.email@example.com\",\n"
		"     \"name\": \"Your Name (optional)\"\n"
		"   }\n"
		"\n"
		"3. Make sure .contact-info.json is listed in .gitignore (it already is by default).\n"
		"\n"
		"The contact file location should be: {repository_root}/.contact-info.json\n"
	)


def load_contact_info(start: Path = None) -> dict[str, str]:
	"""Load and validate contact information from .contact-info.json.
	
	Args:
		start: Starting directory for file search. Defaults to current directory.
	
	Returns:
		Dictionary with at least 'email' key. May include 'name' and other fields.
	
	Raises:
		FileNotFoundError: If .contact-info.json is not found.
		ValueError: If the file is invalid JSON or missing required fields.
	"""
	contact_file = find_contact_file(start)
	
	try:
		with open(contact_file, "r", encoding="utf-8") as f:
			data = json.load(f)
	except json.JSONDecodeError as exc:
		raise ValueError(
			f"Contact file is not valid JSON: {contact_file}\n"
			f"Error: {exc}"
		) from exc
	
	if not isinstance(data, dict):
		raise ValueError(
			f"Contact file must contain a JSON object, not {type(data).__name__}: {contact_file}"
		)
	
	if "email" not in data or not isinstance(data["email"], str) or not data["email"].strip():
		raise ValueError(
			f"Contact file must contain a non-empty 'email' field: {contact_file}\n"
			f"Current content: {data}"
		)
	
	return data


def format_contact_info_for_user_agent(contact_info: dict[str, str]) -> str:
	"""Format contact information for inclusion in User-Agent header.
	
	Args:
		contact_info: Dictionary with 'email' and optional 'name' fields.
	
	Returns:
		Formatted contact string suitable for User-Agent header.
	
	Example:
		>>> info = {"email": "user@example.com", "name": "John Doe"}
		>>> format_contact_info_for_user_agent(info)
		'user@example.com (John Doe)'
		
		>>> info = {"email": "user@example.com"}
		>>> format_contact_info_for_user_agent(info)
		'user@example.com'
	"""
	email = contact_info.get("email", "").strip()
	name = contact_info.get("name", "").strip()
	
	if name:
		return f"{email} ({name})"
	return email
