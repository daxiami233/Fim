/*
 * Copyright (c) 2024 Huawei Device Co., Ltd.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

import { ArkClass, ArkFile, ArkMethod, ArkNamespace, Printer, PrinterBuilder } from 'arkAnalyzer/src';
import { SceneConfig } from 'arkAnalyzer/src/Config';
import { Scene } from 'arkAnalyzer/src/Scene';

let config: SceneConfig = new SceneConfig();

// build from json
config.buildFromJson("./tests/customTest/AppTestConfig.json");
// console.log("config: " + JSON.stringify(config));

function runScene4Json(config: SceneConfig) {
    let projectScene: Scene = new Scene();
    projectScene.buildBasicInfo(config);
    projectScene.buildScene4HarmonyProject();
    projectScene.inferTypes();
    getFiles(projectScene);
    getMethods(projectScene);
    // getCFGs(projectScene);
    
}


function getFiles (projectScene: Scene) {
    let namespaces: ArkNamespace[] = projectScene.getNamespaces();
    let namespaceNames: string[] = namespaces.map(ns => ns.getName()); 
    console.log(namespaceNames);

    let files: ArkFile[] = projectScene.getFiles();
    for (const file of files) {
        console.log(file.getName());
        let printer = new PrinterBuilder();
        printer.dumpToDot(file);
    }
}



function getMethods (projectScene: Scene) {
    let classes: ArkClass[] = projectScene.getClasses(); //let 声明的变量是可变的，即可以在后续代码中重新赋值。显式指定了 classes 的类型为 ArkClass[]（即 ArkClass 类型的数组）。
    let getClassNames : string[] = classes.map(cls => cls.getName());
    console.log(getClassNames);

    const methods = projectScene.getMethods(); // const 声明的变量是不可变的，即不能在后续代码中重新赋值。没有显式指定类型，TypeScript 会根据 projectScene.getClasses() 的返回值自动推断类型。
    console.log("method length: "+ methods.length);
    for (let i = 0; i < methods.length; i++) {
        console.log("method: " + methods[i].getSignature().toString());
        // console.log(methods[i].getCfg());
        // console.log(methods[i].getCfg()?.getDefUseChains());
    }
}

function getCFGs (projectScene: Scene) {
    let methods: ArkMethod[] = projectScene.getMethods();
    let cfgs = methods.map(method => method.getCfg());
    console.log(cfgs[0]);
}

runScene4Json(config);