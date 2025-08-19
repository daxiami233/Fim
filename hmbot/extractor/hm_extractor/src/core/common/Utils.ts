import { ArkAssignStmt, ArkClass, ArkMethod, FileSignature, Local, Scene, Value } from "../../arkanalyzer/src";
import Const from "./Constant";
import fs from "fs";
import path from "path";
import * as JSON5 from "json5";

export default class Utils {
    
    static getValueOfClassFiled(scene: Scene, className: string, filedName: string): Local | undefined {
        let value = undefined;
        scene.getClasses().forEach((clazz: ArkClass) => {
            //find the inner class by name
            if(clazz.getSignature().toString() == className){
                for(const filed of clazz.getFields()){
                    if(filed.getName() == filedName){
                        for(let stmt of filed.getInitializer()){
                            if(stmt instanceof ArkAssignStmt){
                                value = stmt.getRightOp();
                                return value;
                            }
                        } 
                        
                    }
                }
            }
        });
        return value;
    }


    /**
     * 获取方法内给定变量的值
     * @param method 
     * @param targetVar 
     * @param targetValue 
     * @returns 
     */
    static getValueOfVar(method: ArkMethod, targetVar: Local, targetValue: MyValue){
        if(targetValue.historyVals.includes(targetVar)){
            return targetValue;
        }
        targetValue.historyVals.push(targetVar);
        const cfg = method.getBody()?.getCfg();
        for(let unit of cfg?.getStmts()!){
            if(unit instanceof ArkAssignStmt){
                let assignStmt = unit as ArkAssignStmt;
                if(assignStmt.getLeftOp().toString() == targetVar.toString()){
                    if (assignStmt.getRightOp()  instanceof Local){
                        this.getValueOfVar(method, assignStmt.getRightOp() as Local, targetValue);
                    }else{
                        targetValue.value = assignStmt.getRightOp();
                        targetValue.isFinish = true;
                        return targetValue;
                    }
                }
            }
        }
    }

    static getComponentClassOfPage(scene: Scene, module: string, pagePath: string): ArkClass | undefined {
        const signature = new FileSignature(scene.getProjectName(), path.join(module, pagePath));
        const file = scene.getFile(signature);
        const classes = file?.getClasses();
        if(classes != undefined){
            for(const clazz of classes){
                if (clazz.hasComponentDecorator()) { //clazz.hasEntryDecorator() && 
                    return clazz;
                }
            }
        }
    }

    static getJsonFile(module_path: string, signature: string) {
        let json_path: string;
        if (signature.match('^[$]profile:[0-9a-zA-Z_.]+$')) {
            json_path = path.join(module_path, Const.PROFILE_DIR, `${signature.replace('$profile:', '')}.json`)
            if (fs.existsSync(json_path)) {
                let pagesText: string;
                try {
                    pagesText = fs.readFileSync(json_path, 'utf-8');
                } catch (error) {
                    console.log(`Error reading file: ${error}`);
                    return;
                }
                return JSON5.parse(pagesText);
            }
        } else {
            console.log(`String violates the pattern: '^[$]profile:[0-9a-zA-Z_.]+$'`);
            return;
        }
    }
}

export class MyValue{
    historyVals:Value[] = [];
    value:any;
    isFinish: boolean = false;
}
