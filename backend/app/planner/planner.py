from .decisions import Capability, MissingInfo, PlannerDecision
from .state import PlannerState, SearchStatus


class Planner:

    def decide(self, state: PlannerState) -> PlannerDecision:

        # Rules are evaluated in the order a real booking conversation unfolds.

        if state.booking_completed:
            return PlannerDecision(capability=Capability.COMPLETE)

        if not state.specialty_known:
            return PlannerDecision(capability=Capability.MEDICAL)

        if not state.location_known:
            return PlannerDecision(
                capability=Capability.RESPONSE,
                missing_info=[MissingInfo.LOCATION],
            )

        if state.search_status == SearchStatus.NOT_ATTEMPTED:
            return PlannerDecision(capability=Capability.SEARCH)

        if state.search_status == SearchStatus.EMPTY:
            return PlannerDecision(
                capability=Capability.RESPONSE,
                missing_info=[MissingInfo.SEARCH_RESULTS],
            )

        if state.search_status == SearchStatus.HAS_RESULTS and not state.clinic_selected:
            return PlannerDecision(
                capability=Capability.RESPONSE,
                missing_info=[MissingInfo.CLINIC_SELECTION],
            )

        if state.clinic_selected and not state.booking_completed:
            return PlannerDecision(capability=Capability.BOOKING)

        # Fallback — the state was unexpected.
        return PlannerDecision(capability=Capability.RESPONSE)
