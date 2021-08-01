from typing import List
from typing import Tuple

import numpy as np

from ..core.optimizer import Optimizer


class BayesianOptimization(Optimizer):
    def __init__(
        self,
        surrogate_model,
        acquisition_function,
        acqusition_function_opt=None,
    ):
        super().__init__()
        self.surrogate_model = surrogate_model
        self.acquisition_function = acquisition_function
        self.acqusition_function_opt = acqusition_function_opt

    def initialize_model(self, x, y):
        self.update_model(x, y)

    def update_model(self, x, y):
        self.surrogate_model.reset_XY(x, y)
        self.surrogate_model.fit()

        self.acquisition_function.reset_surrogate_model(self.surrogate_model)

        # self.acqusition_function_opt.reset_XY(x, y) # TODO maybe need this later for more advanced acq optimizers

    def propose_new_location(
        self, batch_size: int = 5, pool_size: int = 10
    ) -> Tuple[List, List[float]]:
        # create candidate pool
        pool = self.acqusition_function_opt.sample(
            pool_size
        )  # TODO .create_pool(pool_size)

        pool = np.array(pool).transpose(1, 0)

        # Ask for a location proposal from the acquisition function..
        next_x, eis, _ = self.acquisition_function.propose_location(
            top_n=batch_size, candidates=pool.copy()
        )

        return next_x, eis, pool