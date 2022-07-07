import logging
import os
import re
import venv
import zipfile
from os import listdir
from os.path import isfile
from os.path import join
from pathlib import Path
from typing import Optional
from typing import Sequence

import aws_cdk
import toml
from aws_cdk import Duration
from aws_cdk import aws_codedeploy as codedeploy
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_logs as cwlogs
from constructs import Construct

from infrastructure import clean_name

FILES_TO_ZIP_REGEX = re.compile(".*(\\.py|\\.pyc|.*\\.so\\..*|.*\\.so|.*\\.pem)$")


def get_specific_package_paths(
    specific_packages: Sequence[str],
    site_pkg_folder_path=venv.sysconfig.get_path("platlib"),
):
    paths = []
    for specific_package in specific_packages:
        path_str = os.path.join(site_pkg_folder_path, specific_package)
        regex_query = f"{site_pkg_folder_path}/{specific_package}.*\\.dist-info/RECORD$"
        regex = re.compile(regex_query)
        # look for a top_level.txt
        found = False
        for folder_name, sub_folders, file_names in os.walk(site_pkg_folder_path):
            if found:
                break
            for file_name in file_names:
                if regex.match(f"{folder_name}/{file_name}"):
                    top_level_file = open(f"{folder_name}/{file_name}", "r")
                    # read whole file to a string
                    lines = top_level_file.readlines()
                    for line in lines:
                        entry = line.split(",")[0]
                        if FILES_TO_ZIP_REGEX.match(entry):
                            path_str = os.path.join(site_pkg_folder_path, entry)
                            paths.append(path_str)
                    # close file
                    top_level_file.close()
                    found = True
                    break
        if not found:
            path = Path(path_str)
            if path.exists():
                paths.append(path_str)
    return paths


def get_poetry_dependency_paths(
    site_pkg_folder_path=venv.sysconfig.get_path("platlib"),
    poetry_file_lock: str = ("%s/poetry.lock" % os.getcwd()),
):
    if not os.path.exists(poetry_file_lock):
        raise FileNotFoundError("%s not found" % poetry_file_lock)
    with open(poetry_file_lock, encoding="utf-8") as poetry_file:
        deps = toml.load(poetry_file)
    default_deps = deps["package"]
    paths = []
    for dep in default_deps:
        if dep["category"] != "dev":
            dependency_name = dep["name"]

            snake_case_key = dependency_name.lower().replace("-", "_")
            path_str = os.path.join(site_pkg_folder_path, snake_case_key)

            regex_query = f"{site_pkg_folder_path}/({snake_case_key}|{dependency_name}).*\\.dist-info/RECORD$"
            regex = re.compile(regex_query)

            # look for a top_level.txt
            found = False
            for folder_name, sub_folders, file_names in os.walk(site_pkg_folder_path):
                if found:
                    break
                for file_name in file_names:
                    if regex.match(f"{folder_name}/{file_name}"):
                        top_level_file = open(f"{folder_name}/{file_name}", "r")
                        # read whole file to a string
                        lines = top_level_file.readlines()
                        for line in lines:
                            entry = line.split(",")[0]
                            if FILES_TO_ZIP_REGEX.match(entry):
                                path_str = os.path.join(site_pkg_folder_path, entry)
                                paths.append(path_str)
                        # close file
                        top_level_file.close()
                        found = True
                        break
            if not found:
                path = Path(path_str)
                if path.exists():
                    paths.append(path_str)
    return paths


class CodeZip(Construct):
    __EXCLUDED_PATHS = re.compile(
        r"aws_cdk|boto3|dist\-info|pip|botocore|jsii|docutils|pkg_resources|setuptools|tests|s3transfer|.pyc"
    )

    def __init__(
        self,
        scope: Construct,
        id: str,
        zip_name: str,
        paths_to_zip: None,
        zip_output_dir_path: str = os.path.join(os.getcwd(), ".staging"),
        exclude_regexes=[],
        include_root=True,
        relative_path_prefix=None,
        **kwargs,
    ):

        super().__init__(scope, id)

        # directory_out = os.path.join(os.getcwd(), ".staging")
        self.zip_file = CodeZip.__create_zip(
            zip_name,
            paths_to_zip,
            zip_output_dir_path,
            exclude_regexes,
            include_root,
            relative_path_prefix,
            **kwargs,
        )

        logging.debug(self.zip_file.filename)

    @staticmethod
    def __log():
        return logging.getLogger("infrastructure.constructs.CodeZip")

    @staticmethod
    def __create_zip(
        zip_name,
        paths_to_zip: None,
        zip_output_dir_path: str = ("%s/build" % os.getcwd()),
        exclude_regexes=[],
        include_root=True,
        relative_path_prefix=None,
    ) -> zipfile.ZipFile:
        if not os.path.exists(zip_output_dir_path):
            os.makedirs(zip_output_dir_path)
        if paths_to_zip is None:
            paths_to_zip = []
        zip_output_path = "%s/%s.zip" % (
            zip_output_dir_path,
            zip_name.replace("_", "-"),
        )
        other_excludes_regexes = []
        for exclude_regex in exclude_regexes:
            other_excludes_regexes.append(re.compile(exclude_regex))

        with zipfile.ZipFile(zip_output_path, "w", zipfile.ZIP_DEFLATED) as zip_file:
            for path in paths_to_zip:
                CodeZip.__add_files_to_zip(
                    zip_file,
                    path,
                    other_excludes_regexes=other_excludes_regexes,
                    include_root=include_root,
                    relative_path_prefix=relative_path_prefix,
                )
            return zip_file

    @staticmethod
    def __add_files_to_zip(
        zip_file,
        root_folder_path,
        other_excludes_regexes=[],
        include_root=True,
        relative_path_prefix=None,
    ):
        root = Path(root_folder_path)
        if root.exists() and root.is_dir():
            root_folder = os.walk(root_folder_path)
            for folder_name, sub_folders, file_names in root_folder:
                for file_name in file_names:
                    CodeZip.__zip_it(
                        file_name,
                        folder_name,
                        include_root,
                        other_excludes_regexes,
                        relative_path_prefix,
                        root.name,
                        root_folder_path,
                        zip_file,
                    )

        else:
            file = Path(root_folder_path)

            if file.exists():
                site_pkg_folder_path = venv.sysconfig.get_path("platlib")
                CodeZip.__zip_it(
                    file.name,
                    str(file.parent),
                    include_root,
                    other_excludes_regexes,
                    relative_path_prefix,
                    "site-packages",
                    site_pkg_folder_path,
                    zip_file,
                )
            else:
                print(f"Warning: {root_folder_path} not found")

    @staticmethod
    def __zip_it(
        file_name,
        folder_name,
        include_root,
        other_excludes_regexes,
        relative_path_prefix,
        root_folder_name,
        root_folder_path,
        zip_file,
    ):
        # print(f"folder_name: {folder_name}")
        # print(f"file_name: {file_name}")
        # print(f"include_root: {include_root}")
        # print(f"relative_path_prefix: {relative_path_prefix}")
        # print(f"root_folder_name: {root_folder_name}")
        # print(f"root_folder_path: {root_folder_path}")

        absolute_path = os.path.join(folder_name, file_name)
        if root_folder_name == "site-packages":
            include_root = False
            root_folder_path = root_folder_path + os.path.sep
        relative_path = absolute_path.replace(
            root_folder_path, root_folder_name if include_root else ""
        )
        if relative_path_prefix is not None:
            relative_path = os.path.join(relative_path_prefix, relative_path)
        if CodeZip.__EXCLUDED_PATHS.search(folder_name) is None:
            passed = True
            for other_excludes_regex in other_excludes_regexes:
                if other_excludes_regex.search(relative_path) is not None:
                    passed = False
                    break
            if passed:
                zip_file.write(absolute_path, relative_path)
            # else:
            #     print(f"Exclude:{absolute_path}")


class LayerZip(CodeZip):
    def __init__(
        self,
        scope: Construct,
        id: str,
        layer_name: str,
        runtime: lambda_.Runtime,
        zip_name: str,
        paths_to_zip=get_poetry_dependency_paths(),
        zip_output_dir_path: str = os.path.join(os.getcwd(), ".staging"),
        exclude_regexes=[],
        include_root=True,
        relative_path_prefix=None,
        **kwargs,
    ):
        super().__init__(
            scope,
            id,
            zip_name,
            paths_to_zip,
            zip_output_dir_path,
            exclude_regexes,
            include_root,
            relative_path_prefix,
            **kwargs,
        )
        self.layer = lambda_.LayerVersion(
            self,
            layer_name,
            code=lambda_.Code.from_asset(self.zip_file.filename),
            compatible_runtimes=[runtime],
            removal_policy=aws_cdk.RemovalPolicy.DESTROY,
        )


class LambdaZip(CodeZip):
    def __init__(
        self,
        scope: Construct,
        id: str,
        function_name: str,
        handler: str,
        runtime: lambda_.Runtime,
        environment: {},
        zip_name: str,
        paths_to_zip=[],
        zip_output_dir_path: str = os.path.join(os.getcwd(), ".staging"),
        exclude_regexes=[],
        include_root=True,
        relative_path_prefix=None,
        timeout: Optional[Duration] = None,
        memory_size: int = 256,
        deployment_config: Optional[
            codedeploy.ILambdaDeploymentConfig
        ] = codedeploy.LambdaDeploymentConfig.ALL_AT_ONCE,
        **kwargs,
    ):
        super().__init__(
            scope,
            id,
            zip_name,
            paths_to_zip,
            zip_output_dir_path,
            exclude_regexes,
            include_root,
            relative_path_prefix,
            **kwargs,
        )

        self.function = lambda_.Function(
            self,
            function_name,
            code=lambda_.Code.from_asset(self.zip_file.filename),
            handler=handler,
            runtime=runtime,
            environment=environment,
            timeout=timeout,
            log_retention=cwlogs.RetentionDays.TEN_YEARS,
            memory_size=memory_size,
            function_name=function_name,
        )
        self.version = self.function.current_version
        self.alias = lambda_.Alias(
            self,
            "live",
            alias_name="live",
            version=self.version,
        )
        self.endpoint_application = codedeploy.LambdaApplication(
            self,
            "lambda-application",
            application_name=f"{function_name}-lambda-application",
        )

        self.endpoint_deployment_group = codedeploy.LambdaDeploymentGroup(
            self,
            "deployment-group",
            alias=self.alias,
            deployment_group_name=f"{function_name}-deployment-group",
            deployment_config=deployment_config,
            application=self.endpoint_application,
        )


def __lambda_zip(
    scope: Construct,
    id: str,
    file_name: str,
    path: str,
    function_name: str,
    handler: str,
    environment: dict,
    timeout=Duration.seconds(4),
    memory_size=256,
    deployment_config: codedeploy.LambdaDeploymentConfig = codedeploy.LambdaDeploymentConfig.ALL_AT_ONCE,
) -> LambdaZip:
    only_files = [
        "\\/%s" % f.replace(".", "\\.")
        for f in listdir(path)
        if isfile(join(path, f)) and f != file_name and f != "__init__.py"
    ]
    exclude_regexes = only_files + [
        "/tests/",
        # "\/lib\/",
        "/constructs/",
        ".DS_Store",
    ]
    z = LambdaZip(
        scope,
        id,
        function_name=function_name,
        handler=handler,
        runtime=lambda_.Runtime.PYTHON_3_9,
        zip_name=function_name,
        paths_to_zip=[
            path,
        ],
        exclude_regexes=exclude_regexes,
        include_root=True,
        environment=environment,
        timeout=timeout,
        memory_size=memory_size,
        deployment_config=deployment_config,
    )
    return z


def deps_layer(scope: Construct, branch) -> lambda_.LayerVersion:
    paths_to_zip = get_poetry_dependency_paths() + get_specific_package_paths(["PyJWT"])

    deps_layer_zip = LayerZip(
        scope,
        f"sign-up-list-deps-layer-{clean_name(branch)}",
        f"sign-up-list-deps-layer-{clean_name(branch)}",
        lambda_.Runtime.PYTHON_3_9,
        zip_name=f"sign-up-list-deps-layer-{clean_name(branch)}",
        paths_to_zip=paths_to_zip,
        relative_path_prefix="python/lib/python3.9/site-packages",
    )
    return deps_layer_zip.layer


def flask_endpoint_lambda(scope: Construct, environment: dict, branch: str):
    z = __lambda_zip(
        scope,
        f"sign-up-list-lambda-{clean_name(branch)}",
        "wsgi.py",
        os.path.join(os.getcwd(), "app"),
        f"flask-endpoint-{clean_name(branch)}",
        handler="app.wsgi.lambda_handler",
        environment=environment,
        timeout=Duration.seconds(10),
        memory_size=256,
    )
    return z.function, z.alias
