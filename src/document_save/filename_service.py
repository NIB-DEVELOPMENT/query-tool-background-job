from datetime import datetime
from typing import Optional, Dict
import re


class FilenameService:
    """
    Service for generating standardized, timestamped filenames for query results.

    Format: {timestamp}-{user_id}-{query_name}-{params}.csv
    Example: 20250612-143022-31688-Active-Employee-Email-dept_HR-year_2024.csv

    Features:
    - ISO timestamp at start for chronological sorting
    - Query name with spaces converted to dashes
    - Parameter abbreviation with smart truncation
    - Max 150 character total filename
    """

    MAX_FILENAME_LENGTH = 150
    TIMESTAMP_FORMAT = "%Y%m%d-%H%M%S"

    # Reserved characters that need to be removed/replaced
    INVALID_CHARS_PATTERN = re.compile(r'[<>:"/\\|?*\x00-\x1f]')

    # Maximum lengths for components (leaving room for separators and .csv)
    MAX_TIMESTAMP_LEN = 15  # YYYYMMDD-HHMMSS
    MAX_USERID_LEN = 10
    MAX_QUERYNAME_LEN = 50
    MAX_PARAMS_LEN = 70  # Calculated dynamically
    FILE_EXTENSION = ".csv"

    @classmethod
    def generate_filename(
        cls,
        user_id: int,
        query_name: str,
        query_params: Optional[Dict] = None,
        timestamp: Optional[datetime] = None
    ) -> str:
        """
        Generate a standardized filename for query results.

        Args:
            user_id: ID of the user running the query
            query_name: Name of the query
            query_params: Dictionary of query parameters (optional)
            timestamp: Specific timestamp to use (defaults to now)

        Returns:
            Generated filename string

        Example:
            >>> FilenameService.generate_filename(
                    user_id=31688,
                    query_name="Active Employee Email",
                    query_params={"department": "HR", "year": 2024}
                )
            '20250612-143022-31688-Active-Employee-Email-dept_HR-year_2024.csv'
        """
        # Generate timestamp
        timestamp_str = cls._generate_timestamp(timestamp)

        # Format user ID
        user_id_str = str(user_id)

        # Sanitize query name
        query_name_str = cls._sanitize_query_name(query_name)

        # Format parameters
        params_str = cls._format_parameters(query_params) if query_params else ""

        # Build filename components
        components = [timestamp_str, user_id_str, query_name_str]
        if params_str:
            components.append(params_str)

        # Join and add extension
        filename = "-".join(components) + cls.FILE_EXTENSION

        # Truncate if necessary
        if len(filename) > cls.MAX_FILENAME_LENGTH:
            filename = cls._truncate_filename(
                timestamp_str, user_id_str, query_name_str, params_str
            )

        return filename

    @classmethod
    def _generate_timestamp(cls, timestamp: Optional[datetime] = None) -> str:
        """
        Generate timestamp string in YYYYMMDD-HHMMSS format.

        Args:
            timestamp: Specific datetime to use (defaults to now)

        Returns:
            Formatted timestamp string
        """
        if timestamp is None:
            timestamp = datetime.now()
        return timestamp.strftime(cls.TIMESTAMP_FORMAT)

    @classmethod
    def _sanitize_query_name(cls, query_name: str) -> str:
        """
        Sanitize query name by:
        1. Converting spaces to dashes
        2. Removing invalid filesystem characters
        3. Collapsing multiple dashes

        Args:
            query_name: Raw query name

        Returns:
            Sanitized query name

        Example:
            >>> FilenameService._sanitize_query_name("Active Employee  Email")
            'Active-Employee-Email'
        """
        if not query_name:
            return "unnamed-query"

        # Remove invalid characters
        sanitized = cls.INVALID_CHARS_PATTERN.sub('', query_name)

        # Convert spaces to dashes
        sanitized = sanitized.replace(' ', '-')

        # Collapse multiple dashes
        sanitized = re.sub(r'-+', '-', sanitized)

        # Remove leading/trailing dashes
        sanitized = sanitized.strip('-')

        return sanitized if sanitized else "unnamed-query"

    @classmethod
    def _format_parameters(cls, query_params: Dict) -> str:
        """
        Format query parameters as key_value pairs separated by dashes.

        Args:
            query_params: Dictionary of parameters

        Returns:
            Formatted parameter string

        Example:
            >>> FilenameService._format_parameters(
                    {"department": "HR", "year": 2024, "status": "Active"}
                )
            'dept_HR-status_Active-year_2024'
        """
        if not query_params:
            return ""

        param_pairs = []
        for key, value in sorted(query_params.items()):  # Sort for consistency
            # Abbreviate common parameter names
            abbreviated_key = cls._abbreviate_key(key)

            # Sanitize value
            sanitized_value = cls._sanitize_param_value(value)

            # Create key_value pair
            param_pairs.append(f"{abbreviated_key}_{sanitized_value}")

        return "-".join(param_pairs)

    @classmethod
    def _abbreviate_key(cls, key: str) -> str:
        """
        Abbreviate common parameter key names for brevity.

        Args:
            key: Parameter key name

        Returns:
            Abbreviated key

        Example:
            >>> FilenameService._abbreviate_key("department")
            'dept'
        """
        abbreviations = {
            "department": "dept",
            "employee": "emp",
            "start_date": "sdate",
            "end_date": "edate",
            "status": "sts",
            "category": "cat",
            "identifier": "id",
            "number": "num",
            "amount": "amt",
            "quantity": "qty",
            "description": "desc",
            "reference": "ref",
            "transaction": "txn",
            "account": "acct",
            "customer": "cust",
            "location": "loc",
            "organization": "org",
        }

        lower_key = key.lower()
        return abbreviations.get(lower_key, key[:8])  # Max 8 chars if not abbreviated

    @classmethod
    def _sanitize_param_value(cls, value) -> str:
        """
        Sanitize parameter value for use in filename.

        Args:
            value: Parameter value (can be str, int, etc.)

        Returns:
            Sanitized string value
        """
        # Convert to string
        str_value = str(value)

        # Remove invalid characters
        sanitized = cls.INVALID_CHARS_PATTERN.sub('', str_value)

        # Replace spaces with underscores (not dashes, to distinguish from separators)
        sanitized = sanitized.replace(' ', '_')

        # Collapse multiple underscores
        sanitized = re.sub(r'_+', '_', sanitized)

        # Truncate if too long
        if len(sanitized) > 20:
            sanitized = sanitized[:20]

        return sanitized

    @classmethod
    def _truncate_filename(
        cls,
        timestamp: str,
        user_id: str,
        query_name: str,
        params: str
    ) -> str:
        """
        Intelligently truncate filename to fit within MAX_FILENAME_LENGTH.

        Priority:
        1. Timestamp (always preserved)
        2. User ID (always preserved)
        3. Query name (truncated if needed)
        4. Parameters (truncated if needed)

        Args:
            timestamp: Timestamp string
            user_id: User ID string
            query_name: Query name string
            params: Parameters string

        Returns:
            Truncated filename
        """
        # Calculate available space
        # -4 for .csv, -3 for minimum dashes between components
        available = cls.MAX_FILENAME_LENGTH - len(cls.FILE_EXTENSION) - 3

        # Timestamp and user_id are preserved
        used = len(timestamp) + len(user_id)
        remaining = available - used

        # If no params, just truncate query name
        if not params:
            max_query_len = remaining - 1  # -1 for dash
            truncated_query = query_name[:max_query_len] if len(query_name) > max_query_len else query_name
            return f"{timestamp}-{user_id}-{truncated_query}{cls.FILE_EXTENSION}"

        # Split remaining space between query name and params
        # Give 40% to query name, 60% to params (params are more important for uniqueness)
        query_allocation = int(remaining * 0.4)
        params_allocation = remaining - query_allocation - 1  # -1 for dash

        # Truncate query name
        if len(query_name) > query_allocation:
            truncated_query = query_name[:query_allocation]
            # Try to end at a word boundary
            last_dash = truncated_query.rfind('-')
            if last_dash > query_allocation * 0.7:  # If we're within 30% of the end
                truncated_query = truncated_query[:last_dash]
        else:
            truncated_query = query_name

        # Truncate params
        if len(params) > params_allocation:
            truncated_params = cls._truncate_params_smart(params, params_allocation)
        else:
            truncated_params = params

        return f"{timestamp}-{user_id}-{truncated_query}-{truncated_params}{cls.FILE_EXTENSION}"

    @classmethod
    def _truncate_params_smart(cls, params: str, max_len: int) -> str:
        """
        Intelligently truncate parameters string while preserving as many
        complete key_value pairs as possible.

        Args:
            params: Full parameters string
            max_len: Maximum allowed length

        Returns:
            Truncated parameters string
        """
        # Split into individual param pairs
        param_pairs = params.split('-')

        # Try to fit as many complete pairs as possible
        result_pairs = []
        current_length = 0

        for pair in param_pairs:
            pair_length = len(pair)
            # +1 for the dash separator (except for first pair)
            needed_length = pair_length + (1 if result_pairs else 0)

            if current_length + needed_length <= max_len:
                result_pairs.append(pair)
                current_length += needed_length
            else:
                # Can't fit this pair completely
                # Try to fit a truncated version if this is the first overflow
                if result_pairs:
                    break  # We already have some pairs, stop here
                else:
                    # This is the first pair and it's too long
                    # Truncate it to fit
                    truncated_pair = pair[:max_len]
                    result_pairs.append(truncated_pair)
                    break

        return "-".join(result_pairs)

    @classmethod
    def extract_components(cls, filename: str) -> Dict[str, str]:
        """
        Extract components from a generated filename.
        Useful for testing and validation.

        Args:
            filename: Generated filename

        Returns:
            Dictionary with components: timestamp, user_id, query_name, params

        Example:
            >>> FilenameService.extract_components(
                    '20250612-143022-31688-Active-Employee-Email-dept_HR.csv'
                )
            {
                'timestamp': '20250612-143022',
                'user_id': '31688',
                'query_name': 'Active-Employee-Email',
                'params': 'dept_HR',
                'extension': '.csv'
            }
        """
        # Remove extension
        name_without_ext = filename.rsplit('.', 1)[0]
        extension = filename[len(name_without_ext):]

        # Split on dashes
        parts = name_without_ext.split('-')

        if len(parts) < 3:
            raise ValueError(f"Invalid filename format: {filename}")

        # First two parts are timestamp (YYYYMMDD and HHMMSS)
        timestamp = f"{parts[0]}-{parts[1]}"

        # Third part is user_id
        user_id = parts[2]

        # Everything else is query name and params
        # We need to distinguish between query name and params
        # Params contain underscores, query name uses dashes
        remaining = parts[3:]

        # Find first part that contains underscore (start of params)
        query_parts = []
        param_parts = []
        found_params = False

        for part in remaining:
            if '_' in part or found_params:
                param_parts.append(part)
                found_params = True
            else:
                query_parts.append(part)

        query_name = '-'.join(query_parts) if query_parts else ""
        params = '-'.join(param_parts) if param_parts else ""

        return {
            'timestamp': timestamp,
            'user_id': user_id,
            'query_name': query_name,
            'params': params,
            'extension': extension
        }
