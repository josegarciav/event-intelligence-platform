# RA.co API Field Availability

Reference for RA.co GraphQL API field coverage in the ingestion pipeline.

## Currently Queried (Listing Query)

| GraphQL Field | Mapped To | Notes |
|---|---|---|
| `event.id` | `source_event_id` | |
| `event.title` | `title` | |
| `event.content` | `description` | HTML stripped |
| `event.date` | `date` | |
| `event.startTime` | `start_time` | |
| `event.endTime` | `end_time` | |
| `event.attending` | `going_count` | EngagementMetrics |
| `event.interestedCount` | `interested_count` | EngagementMetrics |
| `event.isTicketed` | `custom_fields.is_ticketed` | |
| `event.cost` | `cost` | Parsed by CurrencyParser |
| `event.contentUrl` | `content_url` | Used to build `source_url` |
| `event.flyerFront` | `flyer_front` | Fallback for `image_url` |
| `event.pick.id` | `pick_id` | RA editor pick |
| `event.pick.blurb` | `pick_blurb` | Stored in `custom_fields` |
| `event.images[0].filename` | `image_filename` | Used to build `image_url` |
| `event.images[0].crop` | `image_crop` | |
| `event.artists[*].name` | `artists` | List of artist names |
| `event.venue.id` | `venue_id` | |
| `event.venue.name` | `venue_name` | |
| `event.venue.address` | `venue_address` | |
| `event.venue.contentUrl` | `venue_content_url` | |
| `event.venue.live` | `venue_live` | Used as `capacity` if int > 0 |
| `event.venue.area.name` | `city` | |
| `event.venue.area.country.name` | `country_name` | |
| `event.venue.area.country.urlCode` | `country_code` | Uppercased |

## Available in Detail Query Only

These fields require a per-event `event(id: $id)` GraphQL call:

| GraphQL Field | Mapped To | Notes |
|---|---|---|
| `event.minimumAge` | `age_restriction` | e.g. "18" |
| `event.venue.location.latitude` | `location.coordinates.latitude` | |
| `event.venue.location.longitude` | `location.coordinates.longitude` | |
| `event.promoters[*].name` | - | Not currently mapped |
| `event.genres[*].name` | - | Not currently mapped |
| `event.tickets[*]` | - | Not currently mapped |

## Available but Not Yet Queried

Fields available in the listing or detail query that we could add:

| GraphQL Field | Potential Use |
|---|---|
| `event.newEventForm` | Draft/published status |
| `event.flags` | Content flags |
| `event.queueItEnabled` | Queue/waitlist indicator |
| `event.embargoDate` | Embargo for press/previews |

## Not Available in RA.co API

These fields in our schema cannot be populated from RA.co:

| Schema Field | Notes |
|---|---|
| `location.postal_code` | Not exposed by RA.co |
| `location.state_or_region` | Not exposed by RA.co |
| `organizer.email` | Not exposed |
| `organizer.phone` | Not exposed |
| `ticket_info.ticket_count_available` | Not exposed |
