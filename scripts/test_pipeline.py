#!/usr/bin/env python3
"""
Simple script to test the Ra.co pipeline execution.

This script demonstrates how to run the Ra.co pipeline and retrieve event data.
"""

import sys
import logging
from pathlib import Path

# Add the project root to the path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

from ingestion.sources.ra_co import RaCoEventPipeline
from ingestion.base_pipeline import PipelineConfig


def main():
    """Run the Ra.co pipeline with test parameters."""
    
    print("\n" + "="*80)
    print("🚀 EVENT INTELLIGENCE PLATFORM - RA.CO PIPELINE TEST")
    print("="*80 + "\n")
    
    # Create pipeline configuration
    print("📋 Creating pipeline configuration...")
    config = PipelineConfig(
        source_name="ra_co",
        base_url="https://ra.co/graphql",
        request_timeout=30,
        max_retries=3,
        batch_size=50,  # Start with smaller batch
        rate_limit_per_second=1,
    )
    
    # Initialize pipeline
    print("🔧 Initializing Ra.co pipeline...")
    pipeline = RaCoEventPipeline(config)
    
    # Execute pipeline with parameters
    print("🌍 Executing pipeline (fetching London events)...\n")
    
    try:
        result = pipeline.execute(
            cities=["Barcelona"],
            days_ahead=180
        )
        
        print("\n" + "="*80)
        print("✅ PIPELINE EXECUTION COMPLETE")
        print("="*80 + "\n")
        
        # Display results
        print(f"📊 EXECUTION SUMMARY:")
        print(f"   Status: {result.status.value}")
        print(f"   Execution ID: {result.execution_id}")
        print(f"   Duration: {result.duration_seconds:.2f} seconds")
        print(f"   Total Events Processed: {result.total_events_processed}")
        print(f"   Successful Events: {result.successful_events}")
        print(f"   Failed Events: {result.failed_events}")
        print(f"   Success Rate: {result.success_rate:.1f}%")
        
        # Display events if any were retrieved
        if result.events:
            print(f"\n📌 SAMPLE EVENTS (showing first 5):\n")
            for idx, event in enumerate(result.events[:5], 1):
                print(f"   {idx}. {event.title}")
                print(f"      City: {event.location.city}")
                print(f"      Date: {event.start_datetime}")
                print(f"      Primary Category: {event.primary_category}")
                print(f"      Quality Score: {event.data_quality_score:.2f}")
                if event.taxonomy_dimensions:
                    print(f"      Taxonomy Mappings:")
                    for dim in event.taxonomy_dimensions[:2]:
                        print(f"        - {dim.primary_category} ({dim.subcategory}): {dim.confidence:.2f}")
                print()
            
            # Show summary
            print(f"   📊 Total unique cities: {len(set(e.location.city for e in result.events))}")
            avg_quality = sum(e.data_quality_score for e in result.events) / len(result.events)
            print(f"   📊 Average quality score: {avg_quality:.2f}")
            
            # Show any errors
            if result.errors:
                print(f"\n⚠️  ERRORS ENCOUNTERED ({len(result.errors)}):")
                for error in result.errors[:5]:
                    print(f"   - {error.get('error', 'Unknown error')}")
                if len(result.errors) > 5:
                    print(f"   ... and {len(result.errors) - 5} more errors")
        else:
            print(f"\n⚠️  NO EVENTS RETRIEVED")
            if result.errors:
                print(f"\n❌ ERRORS:")
                for error in result.errors:
                    print(f"   {error}")
        
        print("\n" + "="*80)
        
        return 0 if result.successful_events > 0 else 1
        
    except Exception as e:
        print(f"\n❌ PIPELINE EXECUTION FAILED:")
        print(f"   {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        print("\n" + "="*80)
        return 1


if __name__ == "__main__":
    sys.exit(main())
