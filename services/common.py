import traceback
from typing import List, Dict, Any,Optional,Union
import contextlib
import pandas as pd
import numpy as np
from db.session import get_db
from sqlalchemy.orm import Session
from sqlalchemy import text, distinct
from streamlit_searchbox import st_searchbox
import streamlit as st


def header_with_progress(question_idx: int, total: int):
    """
    Renders the top-right progress indicator like 'Question (1/5)'.
    """
    cols = st.columns([1, 5, 1])
    with cols[2]:
        st.markdown(f"**Question ({question_idx}/{total})**", unsafe_allow_html=True)



def get_unique_column_values(db: Session, table_class, column_names: list[str]) -> list:
    """
    Fetches unique values of one or more columns from the specified table.

    :param db: SQLAlchemy Session
    :param table_class: SQLAlchemy model class (e.g., Job)
    :param column_names: List of column names as strings
    :return: List of unique values (list of strings if one column, list of tuples if multiple)
    """
    # Validate columns
    columns = []
    for col_name in column_names:
        col = getattr(table_class, col_name, None)
        if col is None:
            raise ValueError(
                f"Column '{col_name}' does not exist in {table_class.__name__} table."
            )
        columns.append(col)

    # Query distinct values
    unique_values = db.query(*columns).distinct().all()

    # Return based on number of columns
    if len(columns) == 1:
        return [value[0] for value in unique_values]  # Flatten for single column
    else:
        return unique_values  # List of tuples for multiple columns

def get_column_value_by_condition(
    db: Session,
    table_class,
    filter_column: str,
    filter_value: Any,
    target_column: Optional[str] = None,
    multiple: bool = False,
) -> Union[Optional[Any], List[Any]]:
    """
    Fetches one or multiple values or full records from table_class
    where filter_column matches filter_value.

    Behavior:
    ----------
    - If multiple=False and target_column=None  -> returns a single full model instance or None
    - If multiple=False and target_column given -> returns a single column value or None
    - If multiple=True and target_column=None   -> returns a list of model instances (possibly empty)
    - If multiple=True and target_column given  -> returns a list of column values (possibly empty)

    Example:
        candidate = get_column_value_by_condition(db, Candidate, "email", user_email)
        print(candidate.name)
    """

    # Validate columns dynamically
    filter_col = getattr(table_class, filter_column, None)
    if filter_col is None:
        raise ValueError(f"Invalid filter column: {filter_column}")

    if target_column is not None:
        target_col = getattr(table_class, target_column, None)
        if target_col is None:
            raise ValueError(f"Invalid target column: {target_column}")

    query = db.query(table_class).filter(filter_col == filter_value)

    # multiple=True  -> return list
    if multiple:
        records = query.all()
        if target_column is None:
            # Return list of full model instances
            return records
        # Return list of specific column values
        return [getattr(r, target_column) for r in records]

    # multiple=False  -> return single
    record = query.first()
    if not record:
        return None

    if target_column is None:
        # Return single full model instance
        return record

    # Return single column value
    return getattr(record, target_column)



def create_searchbox(
    label: str,
    placeholder: str,
    key: str,
    data: list,
    display_fn=lambda x: str(x),
    return_fn=lambda x: x,
) -> str:
    """
    Creates a Streamlit searchbox for selecting an item from data.

    :param label: Label for the searchbox
    :param placeholder: Placeholder text
    :param key: Unique key for Streamlit widget
    :param data: List of items (tuples or single values)
    :param display_fn: Function to format display text (default: str)
    :param return_fn: Function to extract return value (default: identity)
    :return: Selected value based on return_fn
    """
    # Build options dictionary dynamically
    options = {display_fn(item): return_fn(item) for item in data}

    # Search function
    def search_items(search_term: str):
        if not search_term:
            return options
        return [item for item in options if search_term.lower() in item.lower()]

    # Render searchbox
    selected = st_searchbox(
        search_items,
        placeholder=placeholder,
        label=label,
        key=key,
    )
    return options.get(selected)