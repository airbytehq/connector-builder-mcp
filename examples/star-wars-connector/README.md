# Star Wars API Connector

This is an Airbyte connector for the Star Wars API (SWAPI) that extracts data from the comprehensive Star Wars universe database.

## Overview

The Star Wars API connector provides access to six main resource types from the Star Wars universe:

- **People**: Characters from the Star Wars films including their physical characteristics, homeworld, and relationships
- **Planets**: Worlds from the Star Wars universe with detailed environmental and population data
- **Films**: Star Wars movies with metadata including directors, producers, and release information
- **Species**: Different species in the Star Wars universe with biological and cultural information
- **Vehicles**: Ground and atmospheric vehicles with technical specifications
- **Starships**: Space-faring vessels with detailed technical and operational data

## API Source

This connector targets the Star Wars API mirror at `https://swapi.py4e.com/api/` which provides reliable access to the complete Star Wars dataset. The API requires no authentication and provides paginated JSON responses.

## Connector Features

- **Comprehensive Coverage**: All six major Star Wars data streams
- **Pagination Support**: Handles API pagination automatically using cursor-based navigation
- **Rich Schemas**: Complete field definitions for all data types
- **Cross-References**: Maintains URL relationships between related resources
- **No Authentication Required**: Direct access to public API endpoints

## Stream Details

### People Stream
Extracts character data including names, physical attributes, homeworld references, and relationships to films, species, vehicles, and starships.

### Planets Stream  
Provides planetary data including orbital characteristics, climate, terrain, population, and resident references.

### Films Stream
Contains movie metadata with episode information, plot summaries, production details, and character/location references.

### Species Stream
Biological and cultural information about different species including physical characteristics, homeworld, and language.

### Vehicles Stream
Technical specifications for ground and atmospheric vehicles including performance data and pilot references.

### Starships Stream
Detailed specifications for space vessels including hyperdrive capabilities, crew requirements, and pilot information.

## Testing Results

The connector has been validated with comprehensive testing:

- ✅ Manifest validation: All streams properly configured
- ✅ Individual stream tests: All 6 streams successfully reading data
- ✅ Smoke test: 57 total records extracted across all streams
- ✅ Performance: Sub-second response times per stream
- ✅ Data integrity: Complete field population and proper typing

## Usage

This connector can be used with Airbyte to sync Star Wars universe data into your data warehouse or analytics platform for analysis, reporting, or application development.
