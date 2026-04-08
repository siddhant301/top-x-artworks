"""Format raw GraphQL chart data into LLM-friendly text."""

from typing import Any


def _format_currency(value: int | float | None) -> str:
    """Format numeric value as compact USD string for table display."""
    if value is None:
        return "N/A"
    if value >= 1_000_000_000:
        return f"${value/1_000_000_000:.1f}B"
    if value >= 1_000_000:
        return f"${value/1_000_000:.1f}M"
    if value >= 1_000:
        return f"${value/1_000:.1f}K"
    return f"${value:,.0f}"


def _extract_year(key: str) -> str:
    """Extract year from ISO date key (e.g., '2006-01-01T00:00:00.000Z' -> '2006')."""
    return key[:4] if key else ""


def format_chart_data_for_llm(gql_data: dict[str, Any]) -> str:
    """
    Convert raw GraphQL artworks aggregation data into readable text for LLM consumption.

    Args:
        gql_data: Raw GQL response with structure:
            data.artworks.count
            data.artworks.aggregation.saleDate
            data.artworks.aggregation.offerd

    Returns:
        Formatted string suitable for inclusion in an LLM prompt.
    """
    try:
        artworks = gql_data.get("data", {}).get("artworks", {})
    except (AttributeError, TypeError):
        return ""

    count = artworks.get("count", 0)
    aggregation = artworks.get("aggregation", {})
    sale_date_data = aggregation.get("saleDate", [])
    offered_data = {item["key"][:4]: item.get("saleDate", {}).get("offered", 0) for item in aggregation.get("offerd", [])}

    lines = [
        "## Artist Auction Market Data",
        "",
        f"Total artworks in dataset: {count:,}",
        "",
        "### Yearly Auction Performance",
        "",
        "| Year | Lots Sold | Total Realized (USD) | Median Price (USD) | Lots Offered |",
        "|------|-----------|----------------------|-------------------|--------------|",
    ]

    for item in sale_date_data:
        key = item.get("key", "")
        year = _extract_year(key)
        price = item.get("price", {})
        lots_sold = price.get("LotSold", 0)
        realized = price.get("Realized_Auction_Prices", 0)
        median = price.get("Median_Price")
        offered = offered_data.get(year, "—")

        realized_str = _format_currency(realized) if realized else "—"
        median_str = _format_currency(median) if median is not None else "—"

        lines.append(f"| {year} | {lots_sold} | {realized_str} | {median_str} | {offered} |")

    # Add summary statistics
    valid_years = [
        item for item in sale_date_data
        if item.get("price", {}).get("LotSold", 0) > 0
    ]
    if valid_years:
        total_realized = sum(p.get("price", {}).get("Realized_Auction_Prices", 0) for p in valid_years)
        total_lots = sum(p.get("price", {}).get("LotSold", 0) for p in valid_years)
        peak_year = max(valid_years, key=lambda x: x.get("price", {}).get("Realized_Auction_Prices", 0))
        peak_year_label = _extract_year(peak_year.get("key", ""))
        peak_value = peak_year.get("price", {}).get("Realized_Auction_Prices", 0)

        lines.extend([
            "",
            "### Summary",
            "",
            f"- Total lots sold (all years): {total_lots:,}",
            f"- Cumulative realized value: {_format_currency(total_realized)}",
            f"- Peak year by realized value: {peak_year_label} ({_format_currency(peak_value)})",
        ])

    return "\n".join(lines)
