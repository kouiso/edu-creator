"""
=============================================================================
🤖 Agent Prompts (Backstory & Role Definitions)
エージェントプロンプト（バックストーリーと役割定義）
=============================================================================
"""

from prompt.agent.beginner_advocate import (BEGINNER_ADVOCATE_BACKSTORY_TEMPLATE,
                                            BEGINNER_ADVOCATE_GOAL,
                                            BEGINNER_ADVOCATE_ROLE)
from prompt.agent.commander import (COMMANDER_BACKSTORY_TEMPLATE,
                                    COMMANDER_GOAL, COMMANDER_ROLE)
from prompt.agent.content_pm import (CONTENT_PM_BACKSTORY_TEMPLATE,
                                     CONTENT_PM_GOAL, CONTENT_PM_ROLE)
from prompt.agent.product_owner import (PRODUCT_OWNER_BACKSTORY_TEMPLATE,
                                        PRODUCT_OWNER_GOAL, PRODUCT_OWNER_ROLE)
from prompt.agent.quality_pm import (QUALITY_PM_BACKSTORY_TEMPLATE,
                                     QUALITY_PM_GOAL, QUALITY_PM_ROLE)
from prompt.agent.quality_validator import (
    QUALITY_VALIDATOR_BACKSTORY_TEMPLATE, QUALITY_VALIDATOR_GOAL,
    QUALITY_VALIDATOR_ROLE)
from prompt.agent.validator import (VALIDATOR_BACKSTORY_TEMPLATE,
                                    VALIDATOR_GOAL, VALIDATOR_ROLE)
from prompt.agent.scout import SCOUT_BACKSTORY_TEMPLATE, SCOUT_GOAL, SCOUT_ROLE
from prompt.agent.scribe import (SCRIBE_BACKSTORY_TEMPLATE, SCRIBE_GOAL,
                                 SCRIBE_ROLE)
from prompt.agent.router import (ROUTER_BACKSTORY_TEMPLATE, ROUTER_GOAL,
                                 ROUTER_ROLE, ROUTER_SHORT_DESCRIPTION)

__all__ = [
    # Commander
    "COMMANDER_ROLE",
    "COMMANDER_GOAL",
    "COMMANDER_BACKSTORY_TEMPLATE",
    # Scout
    "SCOUT_ROLE",
    "SCOUT_GOAL",
    "SCOUT_BACKSTORY_TEMPLATE",
    # Scribe
    "SCRIBE_ROLE",
    "SCRIBE_GOAL",
    "SCRIBE_BACKSTORY_TEMPLATE",
    # Beginner Advocate
    "BEGINNER_ADVOCATE_ROLE",
    "BEGINNER_ADVOCATE_GOAL",
    "BEGINNER_ADVOCATE_BACKSTORY_TEMPLATE",
    # Content PM
    "CONTENT_PM_ROLE",
    "CONTENT_PM_GOAL",
    "CONTENT_PM_BACKSTORY_TEMPLATE",
    # Quality PM
    "QUALITY_PM_ROLE",
    "QUALITY_PM_GOAL",
    "QUALITY_PM_BACKSTORY_TEMPLATE",
    # Product Owner
    "PRODUCT_OWNER_ROLE",
    "PRODUCT_OWNER_GOAL",
    "PRODUCT_OWNER_BACKSTORY_TEMPLATE",
    # Quality Validator
    "QUALITY_VALIDATOR_ROLE",
    "QUALITY_VALIDATOR_GOAL",
    "QUALITY_VALIDATOR_BACKSTORY_TEMPLATE",
    # Validator
    "VALIDATOR_ROLE",
    "VALIDATOR_GOAL",
    "VALIDATOR_BACKSTORY_TEMPLATE",
    # Router (Task Routing)
    "ROUTER_ROLE",
    "ROUTER_GOAL",
    "ROUTER_BACKSTORY_TEMPLATE",
    "ROUTER_SHORT_DESCRIPTION",
]
