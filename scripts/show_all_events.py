#!/usr/bin/env python3
"""
Display all events retrieved from ra.co pipeline.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from ingestion.sources.ra_co import RaCoEventPipeline
from ingestion.base_pipeline import PipelineConfig

# Create config
config = PipelineConfig(
    source_name="ra_co",
    base_url="https://ra.co/graphql",
    batch_size=100,
    request_timeout=10,
)

# Initialize and run pipeline
pipeline = RaCoEventPipeline(config)
result = pipeline.execute()

print("\n" + "=" * 90)
print("📊 ALL EVENTS RETRIEVED FROM RA.CO")
print("=" * 90)

if result.events:
    print(f"\n✅ Total Events: {len(result.events)}\n")

    for i, event in enumerate(result.events, 1):
        print(f"{i:2d}. {event.title}")
        print(f"    Date: {event.start_datetime}")
        print(f"    Location: {event.location.city}, {event.location.country_code}")
        print(f"    Venue: {event.location.venue_name}")

        # Check for artists in custom_fields
        if event.custom_fields.get("artists"):
            artists = event.custom_fields["artists"]
            if isinstance(artists, list):
                artist_names = [
                    a.get("name", "Unknown") if isinstance(a, dict) else str(a)
                    for a in artists[:3]
                ]
                artists_str = ", ".join(artist_names)
                if len(artists) > 3:
                    artists_str += f", +{len(artists)-3} more"
                print(f"    Artists: {artists_str}")

        print(f"    Quality Score: {event.data_quality_score:.2f}")

        # Show taxonomy
        if event.taxonomy_dimensions:
            for dim in event.taxonomy_dimensions:
                print(
                    f"    📊 {dim.primary_category} → {dim.subcategory} ({dim.confidence:.0%})"
                )

        print()

print("=" * 90)
print(f"✅ Pipeline Status: {result.status}")
print(f"⏱️  Duration: {result.duration_seconds:.2f}s")
print(f"📈 Success Rate: {result.success_rate:.1%}")
print("=" * 90)
