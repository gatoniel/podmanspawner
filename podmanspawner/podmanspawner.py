# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.

# copied from the jupyterhub.spawner.LocalProcessSpawner

import json
import shlex
from subprocess import Popen, PIPE
from traitlets import Any
from traitlets import Bool
from traitlets import default
from traitlets import Dict
from traitlets import Float
from traitlets import Instance
from traitlets import Integer
from traitlets import List
from traitlets import observe
from traitlets import Unicode
from traitlets import Union
from traitlets import validate
from traitlets import Unicode

from jupyterhub.spawner import LocalProcessSpawner, Spawner
from jupyterhub.spawner import set_user_setuid
from jupyterhub.utils import random_port

import jupyterhub

class PodmanSpawner(Spawner):
    """
    A Spawner that uses `subprocess.Popen` to start single-user servers as
    podman containers.
    Requires local UNIX users matching the authenticated users to exist.
    Does not work on Windows.
    """

    popen_kwargs = Dict(
        help="""Extra keyword arguments to pass to Popen
        when spawning single-user servers.
        For example::
            popen_kwargs = dict(shell=True)
        """
    ).tag(config=True)

    cid = Unicode(
        allow_none=True,
        help="""
        The container id (cid) of the single-user server container spawned for current user.
        """,
    )
    image = Unicode(
        "docker.io/jupyterhub/singleuser",
        config=True,
        help="""The image to use for single-user servers.
        This image should have the same version of jupyterhub as
        the Hub itself installed.
        If the default command of the image does not launch
        jupyterhub-singleuser, set `c.Spawner.cmd` to
        launch jupyterhub-singleuser, e.g.
        Any of the jupyter docker-stacks should work without additional config,
        as long as the version of jupyterhub in the image is compatible.
        """,
    ).tag(config=True)
    standard_jupyter_port = Integer(
        8888,
        help="""The standard port, the Jupyter Notebook is listening in the
        container to."""
        )
    https_proxy = Unicode(
        allow_none=True,
        help="""Is your server running behind a proxy? Podman needs to now, to
        pull images correctly."""
        ).tag(config=True)

    podman_additional_cmds = List(
        default_value=[],
        help="""These commands are appended to the podman_base_cmd. They are
        then followed by the jupyter_base_cmd"""
        ).tag(config=True)
    jupyter_additional_cmds = List(
        default_value=[],
        help="""These commands are appended to the jupyter_base_cmd."""
        ).tag(config=True)

    enable_lab = Bool(
        False,
        help="""Enable Jupyter Lab in the container via environment variable.
        Dont forget to change c.Spawner.default_url = '/lab'."""
        )

    env_keep = List(
        [],
        help="""Override the env_keep of the Spawner calls, since we do not need
        to keep these env variables in the container."""
        )


    def make_preexec_fn(self, name):
        """
        Return a function that can be used to set the user id of the spawned process to user with name `name`
        This function can be safely passed to `preexec_fn` of `Popen`
        """
        return set_user_setuid(name)

    def load_state(self, state):
        """Restore state about spawned single-user server after a hub restart.
        Local processes only need the process id.
        """
        super(PodmanSpawner, self).load_state(state)
        if 'cid' in state:
            self.cid = state['cid']

    def get_state(self):
        """Save state that is needed to restore this spawner instance after a hub restore.
        Local processes only need the process id.
        """
        state = super(PodmanSpawner, self).get_state()
        if self.cid:
            state['cid'] = self.cid
        return state

    def clear_state(self):
        """Clear stored state about this spawner (pid)"""
        super(PodmanSpawner, self).clear_state()
        self.cid = None

    def user_env(self, env):
        """Augment environment of spawned process with user specific env variables."""
        import pwd

        env['USER'] = self.user.name
        home = pwd.getpwnam(self.user.name).pw_dir
        shell = pwd.getpwnam(self.user.name).pw_shell
        # These will be empty if undefined,
        # in which case don't set the env:
        if home:
            env['HOME'] = home
        if shell:
            env['SHELL'] = shell
        return env

    def get_env(self):
        """Get the complete set of environment variables to be set in the spawned process."""
        env = super().get_env()
        env = self.user_env(env)
        if self.https_proxy:
            env['https_proxy'] = self.https_proxy
        if self.enable_lab:
            env['JUPYTER_ENABLE_LAB'] = "yes"
        env["JUPYTER_IMAGE_SPEC"] = self.image
        return env

    async def move_certs(self, paths):
        """Takes cert paths, moves and sets ownership for them
        Arguments:
            paths (dict): a list of paths for key, cert, and CA
        Returns:
            dict: a list (potentially altered) of paths for key, cert,
            and CA
        Stage certificates into a private home directory
        and make them readable by the user.
        """
        raise NotImplementedError
        import pwd

        key = paths['keyfile']
        cert = paths['certfile']
        ca = paths['cafile']

        user = pwd.getpwnam(self.user.name)
        uid = user.pw_uid
        gid = user.pw_gid
        home = user.pw_dir

        # Create dir for user's certs wherever we're starting
        hub_dir = "{home}/.jupyterhub".format(home=home)
        out_dir = "{hub_dir}/jupyterhub-certs".format(hub_dir=hub_dir)
        shutil.rmtree(out_dir, ignore_errors=True)
        os.makedirs(out_dir, 0o700, exist_ok=True)

        # Move certs to users dir
        shutil.move(paths['keyfile'], out_dir)
        shutil.move(paths['certfile'], out_dir)
        shutil.copy(paths['cafile'], out_dir)

        key = os.path.join(out_dir, os.path.basename(paths['keyfile']))
        cert = os.path.join(out_dir, os.path.basename(paths['certfile']))
        ca = os.path.join(out_dir, os.path.basename(paths['cafile']))

        # Set cert ownership to user
        for f in [hub_dir, out_dir, key, cert, ca]:
            shutil.chown(f, user=uid, group=gid)

        return {"keyfile": key, "certfile": cert, "cafile": ca}

    async def start(self):
        """Start the single-user server."""
        import pwd
        user = pwd.getpwnam(self.user.name)
        uid = user.pw_uid
        gid = user.pw_gid
        hosthome = user.pw_dir
        conthome = "/home/jovyan/home"#{}".format(self.user.name)

        self.port = random_port()

        podman_base_cmd = [
                "podman", "run", "-d", "--env-host",
                # "--rm",
                "-u", "{}:{}".format(uid, gid),
                # "-p", "{hostport}:{port}".format(
                #         hostport=self.port, port=self.standard_jupyter_port
                #         ),
                "--net", "host",
                "-v", "{}:/home/jovyan/home"#".format(hosthome, conthome),
                ]

        jupyter_base_cmd = [
                self.image, "start-notebook.sh",
                "--NotebookApp.port={}".format(self.port)
                ]
        podman_cmd = podman_base_cmd+self.podman_additional_cmds
        jupyter_cmd = jupyter_base_cmd+self.jupyter_additional_cmds

        cmd = shlex.split(" ".join(podman_cmd+jupyter_cmd))

        env = self.get_env()

        self.log.info("Spawning via Podman command: %s", ' '.join(s for s in cmd))

        popen_kwargs = dict(
            preexec_fn=self.make_preexec_fn(self.user.name),
            stdout=PIPE, stderr=PIPE,
            start_new_session=True,  # don't forward signals
        )
        popen_kwargs.update(self.popen_kwargs)
        # don't let user config override env
        popen_kwargs['env'] = env
        try:
            # https://stackoverflow.com/questions/2502833/store-output-of-subprocess-popen-call-in-a-string
            proc = Popen(cmd, **popen_kwargs)
            output, err = proc.communicate()
            if proc.returncode == 0:
                self.cid = output[:-2]
            else:
                self.log.error(
                        "PodmanSpawner.start error: {}".format(err)
                        )
                raise RuntimeError(err)
        except PermissionError:
            # use which to get abspath
            script = shutil.which(cmd[0]) or cmd[0]
            self.log.error(
                "Permission denied trying to run %r. Does %s have access to this file?",
                script,
                self.user.name,
            )
            raise
        return ('127.0.0.1', self.port)

    async def poll(self):
        """Poll the spawned process to see if it is still running.
        If the process is still running, we return None. If it is not running,
        we return the exit code of the process if we have access to it, or 0 otherwise.
        """
        output, err, returncode = self.podman("inspect")
        if returncode == 0:
            state = json.loads(output)[0]["State"]
            if state["Running"]:
                return None
            else:
                return state["ExitCode"]
        else:
            self.log.error(
                    "PodmanSpawner.poll error: {}".format(err)
                    )
            raise RuntimeError(err)

    def podman(self, command):
        cmd = "podman container {command} {cid}".format(
                command=command, cid=self.cid
                )
        env = self.get_env()
        popen_kwargs = dict(
                preexec_fn=self.make_preexec_fn(self.user.name),
                stdout=PIPE, stderr=PIPE,
                start_new_session=True,  # don't forward signals
                )
        popen_kwargs['env'] = env
        proc = Popen(shlex.split(cmd), **popen_kwargs)
        output, err = proc.communicate()
        return output, err, proc.returncode

    async def stop(self, now=False):
        """Stop the single-user server process for the current user.
        If `now` is False (default), shutdown the server as gracefully as possible,
        e.g. starting with SIGINT, then SIGTERM, then SIGKILL.
        If `now` is True, terminate the server immediately.
        The coroutine should return when the process is no longer running.
        """
        output, err, returncode = self.podman("stop")
        if returncode == 0:
            output, err, returncode = self.podman("rm")
            if not returncode == 0:
                self.log.warn(
                        "PodmanSpawner.stop warn: {}".format(err)
                        )
            return
        else:
            self.log.error(
                    "PodmanSpawner.stop error: {}".format(err)
                    )
            raise RuntimeError(err)
