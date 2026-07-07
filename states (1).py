from aiogram.fsm.state import State, StatesGroup


class GenerateImageStates(StatesGroup):
    waiting_for_prompt = State()


class EditImageStates(StatesGroup):
    waiting_for_instruction = State()  # user sent a photo, waiting for edit text


class SalesStates(StatesGroup):
    waiting_for_receipt = State()  # user selected a service, waiting for payment receipt
