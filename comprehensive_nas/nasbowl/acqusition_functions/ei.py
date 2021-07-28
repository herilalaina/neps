import networkx as nx
import numpy as np
import torch

from nasbowl.acqusition_functions.base_acqusition import BaseAcquisition


class ComprehensiveExpectedImprovement(BaseAcquisition):
    def __init__(self, surrogate_model, augmented_ei=False, xi: float = 0.0,
                 in_fill: str = 'best', strategy=None,
                 iters=0):
        """
        This is the graph BO version of the expected improvement
        key differences are:
        1. The input x2 is a networkx graph instead of a vectorial input
        2. the search space (a collection of x1_graphs) is discrete, so there is no gradient-based optimisation. Instead,
        we compute the EI at all candidate points and empirically select the best position during optimisation

        augmented_ei: Using the Augmented EI heuristic modification to the standard expected improvement algorithm
        according to Huang (2006)
        xi: float: manual exploration-exploitation trade-off parameter.
        in_fill: str: the criterion to be used for in-fill for the determination of mu_star. 'best' means the empirical
        best observation so far (but could be susceptible to noise), 'posterior' means the best *posterior GP mean*
        encountered so far, and is recommended for optimisationn of more noisy functions.
        :param target_fidelity:
        """
        super(ComprehensiveExpectedImprovement, self).__init__(surrogate_model=surrogate_model,
                                                               strategy=strategy, iters=iters)

        assert in_fill in ['best', 'posterior']
        self.in_fill = in_fill
        self.augmented_ei = augmented_ei
        self.xi = xi

    def eval(self, x_graphs, x_hps, asscalar=False):
        """
        Return the negative expected improvement at the query point x2
        """
        from torch.distributions import Normal
        try:
            mu, cov = self.surrogate_model.predict(x_graphs, x_hps)
        except:
            return -1.  # in case of error. return ei of -1
        std = torch.sqrt(torch.diag(cov))
        mu_star = self._get_incumbent()
        gauss = Normal(torch.zeros(1, device=mu.device), torch.ones(1, device=mu.device))
        u = (mu - mu_star - self.xi) / std
        ucdf = gauss.cdf(u)
        updf = torch.exp(gauss.log_prob(u))
        ei = std * updf + (mu - mu_star - self.xi) * ucdf
        if self.augmented_ei:
            sigma_n = self.surrogate_model.likelihood
            ei *= (1. - torch.sqrt(torch.tensor(sigma_n, device=mu.device)) / torch.sqrt(sigma_n + torch.diag(cov)))
        if asscalar:
            ei = ei.detach().numpy().item()
        return ei

    def _get_incumbent(self, ):
        """
        Get the incumbent
        """
        if self.in_fill == 'max':
            return torch.max(self.surrogate_model.y_)
        else:
            x = self.surrogate_model.x
            mu_train, _ = self.surrogate_model.predict(x)
            incumbent_idx = torch.argmax(mu_train)
            return self.surrogate_model.y_[incumbent_idx]

    def propose_location(self, candidates, top_n=5, return_distinct=True):
        """top_n: return the top n candidates wrt the acquisition function."""
        # selected_idx = [i for i in self.candidate_idx if self.evaluated[i] is False]
        # eis = torch.tensor([self.eval(self.candidates[c]) for c in selected_idx])
        # print(eis)
        self.iters += 1
        if return_distinct:
            eis = np.array([self.eval(c_graphs, c_hps) for c_graphs, c_hps in candidates])
            eis_, unique_idx = np.unique(eis, return_index=True)
            try:
                i = np.argpartition(eis_, -top_n)[-top_n:]
                indices = np.array([unique_idx[j] for j in i])
            except ValueError:
                eis = torch.tensor([self.eval(c) for c in candidates])
                values, indices = eis.topk(top_n)
        else:
            eis = torch.tensor([self.eval(c) for c in candidates])
            values, indices = eis.topk(top_n)
        xs = tuple([candidates[int(i)] for i in indices])
        return xs, eis, indices

    def optimize(self):
        raise ValueError("The kernel invoked does not have hyperparameters to optimse over!")