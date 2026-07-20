"""Platform middle layer for the AI merchant operations workspace.

This package is the architectural boundary confirmed in the product docs:
platforms are Connectors, AI calls go through AI Engine, and automation goes
through Workflow. Existing endpoints may keep their public contracts while
moving implementation behind these interfaces.
"""

